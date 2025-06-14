import datetime
import logging
import os
from decimal import Decimal
from typing import List, Optional

import aioboto3
from agents._config import set_default_openai_key
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv

from agents import Agent, ModelSettings, WebSearchTool
from app.agents.schemas.achivement_schemas import AchievementDTO
from app.agents.schemas.agent_schemas import AgentDTO
from app.agents.schemas.chat_schemas import AiAgentMessageDTO, ChatMessageDTO

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

load_dotenv()


class DynamoDBManager:
    def __init__(self):
        self.session = aioboto3.Session()
        self.region_name = "ap-northeast-2"
        self.table_name = "map_agents"
        self.chat_history_table_name = "map_agent_history"
        # 챗봇 업적 테이블 이름
        self.achievement_table_name = "map_agent_achievements"
        # 챗봇 업적 사용자 테이블 이름
        self.user_achievement_table_name = "map_user_achievements"


class AgentManager(DynamoDBManager):
    def __init__(self):
        super().__init__()
        self.set_default_openai_key()

    def set_default_openai_key(self):
        set_default_openai_key(os.getenv("OPENAI_API_KEY"), True)

    async def get_agent(self, agent_id: str) -> Optional[AgentDTO]:
        """
        에이전트 아이디로 단일 에이전트를 조회합니다.
        :param agent_id: 조회할 에이전트의 ID
        :return: 조회된 AgentDTO 또는 None
        """
        async with self.session.resource(
            "dynamodb", region_name=self.region_name
        ) as dynamodb:
            table = await dynamodb.Table(self.table_name)
            response = await table.get_item(Key={"agent_id": agent_id})
            item = response.get("Item")
            if item is None:
                return None
            return AgentDTO(**item)

    async def list_agents(self) -> List[AgentDTO]:
        """
        테이블에 저장된 모든 에이전트를 조회합니다.
        최신순으로 정렬합니다.
        :return: AgentDTO 리스트
        """
        async with self.session.resource(
            "dynamodb", region_name=self.region_name
        ) as dynamodb:
            table = await dynamodb.Table(self.table_name)
            response = await table.scan()
            items = response.get("Items", [])
            return [AgentDTO(**item) for item in items]

    async def filter_agents(self, latitude: float, longitude: float) -> List[AgentDTO]:
        """
        위도/경도 기준으로 반경 1000m 이내의 에이전트를 조회합니다.
        :param latitude: 중심 위도
        :param longitude: 중심 경도
        :return: AgentDTO 리스트
        """
        try:
            lat_min = Decimal(str(latitude - 0.009))  # ~1000m
            lat_max = Decimal(str(latitude + 0.009))
            lon_min = Decimal(str(longitude - 0.009))
            lon_max = Decimal(str(longitude + 0.009))

            async with self.session.resource(
                "dynamodb", region_name=self.region_name
            ) as dynamodb:
                table = await dynamodb.Table(self.table_name)

                # 스캔 작업으로 필터링
                response = await table.scan(
                    FilterExpression="latitude >= :lat_min AND latitude <= :lat_max AND longitude >= :lon_min AND longitude <= :lon_max",
                    ExpressionAttributeValues={
                        ":lat_min": lat_min,
                        ":lat_max": lat_max,
                        ":lon_min": lon_min,
                        ":lon_max": lon_max,
                    },
                )

                logger.info(f"response: {response}")
                items = response.get("Items", [])
                return [AgentDTO(**item) for item in items]
        except Exception as e:
            logger.error(f"Error filtering agents: {str(e)}")
            return []

    async def register_agent(self, agent: AgentDTO):
        # 에이전트 등록
        async with self.session.resource(
            "dynamodb", region_name=self.region_name
        ) as dynamodb:
            table = await dynamodb.Table(self.table_name)
            await table.put_item(Item=agent.model_dump())

    async def delete_agent(self, agent_id: str):
        # 에이전트 삭제
        async with self.session.resource(
            "dynamodb", region_name=self.region_name
        ) as dynamodb:
            table = await dynamodb.Table(self.table_name)
            await table.delete_item(Key={"agent_id": agent_id})

    # Agent DTO 기반으로 에이전트 만들어야함
    async def load_agent(self, agent_id: str):
        # 에이전트 정보 로드
        agent_dto = await self.get_agent(agent_id)
        agent = Agent(
            name=agent_dto.name,
            instructions=f"""
            당신은 {agent_dto.name} 에이전트 챗봇 입니다.
            * 주어진 정보 외의 정보는 웹검색 툴을 기반으로, 최신 정보를 검색해서 반드시 {datetime.datetime.now().strftime('%Y')} 년도 기준 최신 정보로 답변해야 합니다.
            * 웹검색 기반으로 답변 시, 해당 챗봇과 관련없는 내용은 답변하면 안됩니다.
            * 출력 토큰은 170 토큰 미만으로 만 사용해야 합니다.
            * 170 토큰 이상 사용 시 다시 답변을 준비해야합니다.

            # 프롬프트(역할)
            {agent_dto.prompt}
            """,
            tools=[WebSearchTool()],
            model=agent_dto.model,
            model_settings=ModelSettings(
                tool_choice="auto",
                parallel_tool_calls=True,
                truncation="auto",
                temperature=0.2,  # 결정적 응답으로 속도 향상
                frequency_penalty=0.1,
                presence_penalty=0.1,
                max_tokens=169,  # 필요한 만큼만 토큰 생성
            ),
        )
        return agent

    async def save_chat_history(self, chat_message: ChatMessageDTO):
        chat_message.timestamp = datetime.datetime.now().isoformat()
        item = chat_message.model_dump()
        item["sub#agent_id"] = f"{chat_message.sub}#{chat_message.agent_id}"
        async with self.session.resource(
            "dynamodb", region_name=self.region_name
        ) as dynamodb:
            table = await dynamodb.Table(self.chat_history_table_name)
            await table.put_item(Item=item)

    async def get_chat_history(self, sub: str, agent_id: str) -> List[ChatMessageDTO]:
        """
        특정 사용자와 에이전트 간의 채팅 히스토리를 시간순으로 조회합니다.
        :param sub: 사용자 식별자
        :param agent_id: 에이전트 ID
        :return: 시간순으로 정렬된 ChatMessageDTO 리스트
        """
        try:
            async with self.session.resource(
                "dynamodb", region_name=self.region_name
            ) as dynamodb:
                table = await dynamodb.Table(self.chat_history_table_name)
                response = await table.query(
                    KeyConditionExpression=Key("sub#agent_id").eq(f"{sub}#{agent_id}"),
                    ScanIndexForward=True,  # 오름차순 정렬 (과거 -> 최신)
                    Limit=50,  # 최근 50개 메시지만 조회
                )
                items = response.get("Items", [])
                return [AiAgentMessageDTO(**item) for item in items]
        except Exception as e:
            logger.error(f"채팅 히스토리 조회 중 오류 발생: {str(e)}")
            return []

    async def get_chat_list(self, sub: str) -> List[AgentDTO]:
        """
        특정 사용자의 챗봇과의 대화 내역을 조회합니다.
        특정 챗봇과의 대화를 진행한 경우에만 필터링 되어 조회
        agent_id 기준으로 중복 없이 조회
        :param sub: 사용자 식별자
        :return: 시간순으로 정렬된 AgentDTO 리스트
        """
        try:
            async with self.session.resource(
                "dynamodb", region_name=self.region_name
            ) as dynamodb:
                table = await dynamodb.Table(self.chat_history_table_name)
                # scan 작업으로 sub 필터링하여 agent_id 목록 가져오기
                scan_response = await table.scan(
                    FilterExpression="begins_with(#sub_agent_id, :sub_prefix)",
                    ExpressionAttributeNames={"#sub_agent_id": "sub#agent_id"},
                    ExpressionAttributeValues={":sub_prefix": f"{sub}#"},
                    ProjectionExpression="agent_id",
                )
                unique_agent_ids = list(
                    set(item["agent_id"] for item in scan_response.get("Items", []))
                )
                # 각 agent_id에 대해 가장 최근 대화 조회
                latest_chats = []
                for agent_id in unique_agent_ids:
                    # 각 agent_id별로 가장 최근 대화 조회
                    query_response = await table.query(
                        KeyConditionExpression=Key("sub#agent_id").eq(
                            f"{sub}#{agent_id}"
                        ),
                        ScanIndexForward=False,  # 내림차순 정렬 (최신순)
                        Limit=1,  # 가장 최근 1개만 조회
                    )

                    if query_response.get("Items"):
                        latest_item = query_response["Items"][0]
                        latest_chats.append(
                            {
                                "agent_id": latest_item["agent_id"],
                                "content": latest_item["content"],
                                "timestamp": latest_item["timestamp"],
                            }
                        )
                # latest_chats 정렬 최신 시간순으로
                latest_chats.sort(key=lambda x: x["timestamp"], reverse=True)
                return latest_chats
        except Exception as e:
            logger.error(f"채팅 히스토리 조회 중 오류 발생: {str(e)}")
            return []

    async def delete_agent_history(
        self, sub: str, agent_id: str
    ) -> List[ChatMessageDTO]:
        async with self.session.resource(
            "dynamodb", region_name=self.region_name
        ) as dynamodb:
            table = await dynamodb.Table(self.chat_history_table_name)

            # 먼저 해당 파티션 키의 모든 아이템을 조회
            response = await table.query(
                KeyConditionExpression=Key("sub#agent_id").eq(f"{sub}#{agent_id}")
            )

            # 각 아이템을 삭제
            for item in response.get("Items", []):
                await table.delete_item(
                    Key={
                        "sub#agent_id": f"{sub}#{agent_id}",
                        "timestamp": item["timestamp"],
                    }
                )

            return {"message": "success"}

    async def update_agent_prompt(
        self, agent_id: str, new_prompt: str
    ) -> Optional[AgentDTO]:
        """
        에이전트의 프롬프트를 수정합니다.
        :param agent_id: 수정할 에이전트의 ID
        :param new_prompt: 새로운 프롬프트
        :return: 수정된 AgentDTO 또는 None (에이전트가 존재하지 않는 경우)
        """
        try:
            async with self.session.resource(
                "dynamodb", region_name=self.region_name
            ) as dynamodb:
                table = await dynamodb.Table(self.table_name)

                # 에이전트 존재 여부 확인
                agent = await self.get_agent(agent_id)
                if agent is None:
                    logger.error(f"에이전트를 찾을 수 없습니다: {agent_id}")
                    return None

                # 프롬프트 업데이트
                response = await table.update_item(
                    Key={"agent_id": agent_id},
                    UpdateExpression="SET prompt = :prompt",
                    ExpressionAttributeValues={":prompt": new_prompt},
                    ReturnValues="ALL_NEW",
                )

                updated_item = response.get("Attributes")
                if updated_item:
                    return AgentDTO(**updated_item)
                return None

        except Exception as e:
            logger.error(f"에이전트 프롬프트 수정 중 오류 발생: {str(e)}")
            return None

    async def add_achievement_to_agent(
        self, agent_id: str, achievements: List[AchievementDTO]
    ) -> Optional[AgentDTO]:
        """
        에이전트의 업적을 추가 합니다.
        :param agent_id: 수정할 에이전트의 ID
        :param achievements: 추가할 업적 리스트
        :return: 수정된 AgentDTO 또는 None (에이전트가 존재하지 않는 경우)
        """
        try:
            async with self.session.resource(
                "dynamodb", region_name=self.region_name
            ) as dynamodb:
                table = await dynamodb.Table(self.table_name)

                # 에이전트 존재 여부 확인
                agent = await self.get_agent(agent_id)
                if agent is None:
                    logger.error(f"에이전트를 찾을 수 없습니다: {agent_id}")
                    return None

                for achievement in achievements:
                    print(achievement)
                    logger.info(f"achievement: {achievement}")

                # 현재 업적 개수 확인
                current_agent = await self.get_agent(agent_id)
                current_achievements = current_agent.achievements or []

                # 업적이 30개 이상이면 추가하지 않음
                if len(current_achievements) >= 30:
                    logger.warning(
                        f"에이전트 {agent_id}의 업적이 이미 30개 이상입니다. 추가 업적이 무시됩니다."
                    )
                    return current_agent

                # DynamoDB 업적 리스트 형식으로 변환
                achievement_dicts = [
                    achievement.model_dump() for achievement in achievements
                ]

                # 남은 업적 슬롯 계산
                remaining_slots = 30 - len(current_achievements)
                if len(achievement_dicts) > remaining_slots:
                    achievement_dicts = achievement_dicts[:remaining_slots]
                    logger.warning(
                        f"업적이 {remaining_slots}개만 추가됩니다. (최대 30개 제한)"
                    )

                response = await table.update_item(
                    Key={"agent_id": agent_id},
                    UpdateExpression="SET achievements = list_append(if_not_exists(achievements, :empty_list), :achievements)",
                    ExpressionAttributeValues={
                        ":achievements": achievement_dicts,
                        ":empty_list": [],
                    },
                    ReturnValues="ALL_NEW",
                )

                updated_agent = await self.get_agent(agent_id)
                return updated_agent

        except Exception as e:
            logger.error(f"에이전트 프롬프트 수정 중 오류 발생: {str(e)}")
            return None
