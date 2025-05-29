import datetime
from typing import List, Optional
import boto3
import os


import logging
from agents import Agent, ModelSettings
from agents._config import set_default_openai_key
from dotenv import load_dotenv
from boto3.dynamodb.conditions import Key
from app.agents.schemas.agent_schemas import AgentDTO
from app.agents.schemas.chat_schemas import AiAgentMessageDTO, ChatMessageDTO


logger = logging.getLogger(__name__)

load_dotenv()

# 다이나모 디비에 등록된 에이전트 정보 조회 및 등록 API


class AgentManager:
    def __init__(self):
        self.set_default_openai_key()
        self.dynamodb = boto3.resource(
            "dynamodb",
            region_name="ap-northeast-2"
        )
        self.table = self.dynamodb.Table("map_agents")
        self.chat_history = self.dynamodb.Table("map_agent_history")

    def set_default_openai_key(self):
        set_default_openai_key(os.getenv("OPENAI_API_KEY"), True)

    def get_agent(self, agent_id: str) -> Optional[AgentDTO]:
        """
        에이전트 아이디로 단일 에이전트를 조회합니다.
        :param agent_id: 조회할 에이전트의 ID
        :return: 조회된 AgentDTO 또는 None
        """
        response = self.table.get_item(Key={"agent_id": agent_id})
        item = response.get("Item")
        if item is None:
            return None
        return AgentDTO(**item)

    def list_agents(self) -> List[AgentDTO]:
        """
        테이블에 저장된 모든 에이전트를 조회합니다.
        최신순으로 정렬합니다.
        :return: AgentDTO 리스트
        """
        response = self.table.scan()
        items = response.get("Items", [])
        return [AgentDTO(**item) for item in items]

    def filter_agents(self, latitude: float, longitude: float) -> List[AgentDTO]:
        """
        위도/경도 기준으로 반경 500m 이내의 에이전트를 조회합니다.
        :param latitude: 중심 위도
        :param longitude: 중심 경도
        :return: AgentDTO 리스트
        """
        try:
            # 위도/경도 기반 500m 반경 내 에이전트 필터링
            response = self.table.query(
                IndexName="LocationIndex",
                KeyConditionExpression=(
                    "latitude BETWEEN :lat_min AND :lat_max AND "
                    "longitude BETWEEN :lon_min AND :lon_max"
                ),
                ExpressionAttributeValues={
                    ":lat_min": latitude - 0.0045,  # ~500m
                    ":lat_max": latitude + 0.0045,
                    ":lon_min": longitude - 0.0045,
                    ":lon_max": longitude + 0.0045
                }
            )
            items = response.get("Items", [])
            return [AgentDTO(**item) for item in items]
        except Exception as e:
            logger.error(f"Error filtering agents: {str(e)}")
            return []

    def register_agent(self, agent: AgentDTO):
        # 에이전트 등록
        self.table.put_item(Item=agent.model_dump())

    def delete_agent(self, agent_id: str):
        # 에이전트 삭제
        self.table.delete_item(Key={"id": agent_id})

    # Agent DTO 기반으로 에이전트 만들어야함
    def load_agent(self, agent_id: str):
        # 에이전트 정보 로드
        agent_dto = self.get_agent(agent_id)
        agent = Agent(
            name=agent_dto.name,
            instructions=agent_dto.prompt,
            tools=[],
            model=agent_dto.model,
            model_settings=ModelSettings(
                temperature=0.1,  # 결정적 응답으로 속도 향상
                max_tokens=150,  # 필요한 만큼만 토큰 생성
            ),
        )
        return agent

    def save_chat_history(self, chat_message: ChatMessageDTO):
        chat_message.timestamp = datetime.datetime.now().isoformat()
        item = chat_message.model_dump()
        item["sub#agent_id"] = f"{chat_message.sub}#{chat_message.agent_id}"
        self.chat_history.put_item(Item=item)

    def get_chat_history(self, sub: str, agent_id: str) -> List[ChatMessageDTO]:
        """
        특정 사용자와 에이전트 간의 채팅 히스토리를 시간순으로 조회합니다.
        :param sub: 사용자 식별자
        :param agent_id: 에이전트 ID
        :return: 시간순으로 정렬된 ChatMessageDTO 리스트
        """
        try:
            response = self.chat_history.query(
                KeyConditionExpression=Key("sub#agent_id").eq(f"{sub}#{agent_id}"),
                ScanIndexForward=True,  # 오름차순 정렬 (과거 -> 최신)
                Limit=50  # 최근 50개 메시지만 조회
            )
            items = response.get("Items", [])
            return [AiAgentMessageDTO(**item) for item in items]
        except Exception as e:
            logger.error(f"채팅 히스토리 조회 중 오류 발생: {str(e)}")
            return []
