import datetime
import logging
import os
import uuid
from decimal import Decimal
from typing import List, Optional

import aioboto3
import httpx
from agents._config import set_default_openai_key
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv
from fastapi import Request

from agents import Agent, ModelSettings, WebSearchTool
from app.agents.core.user_manager import UserManager
from app.agents.schemas.achivement_schemas import AchievementDTO
from app.agents.schemas.agent_schemas import AgentDTO
from app.agents.schemas.chat_schemas import (
    AiAgentMessageDTO,
    ChatListDTO,
    ChatMessageDTO,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

load_dotenv()


class DynamoDBManager:
    def __init__(self):
        self.session = aioboto3.Session()
        self.region_name = "ap-northeast-2"
        self.table_name = "map_agents"
        self.chat_history_table_name = "map_agent_history"
        self.user_achievement_table_name = (
            "map_user_achievements"  # 챗봇 업적 사용자 테이블 이름
        )


class AgentManager(DynamoDBManager):
    def __init__(self):
        super().__init__()
        self.set_default_openai_key()
        self.judgement_agent = Agent[None](
            name="AchievementJudgement",
            instructions="""
            당신의 역할은 특정 챗봇의 업적 달성 여부를 판단하는 판단자 입니다.
            주어진 대화 내용을 통해 업적 달성 여부를 판단해야합니다.

            업적 달성 조건은 업적 달성 조건을 확인해보고 판단해야해.
            * 업적 달성 한 경우, 달성한 업적 리스트를 반환합니다.
            * 업적 달성 하지 못한 경우, 빈 리스트를 반환합니다.
            """,
            model="gpt-4o-mini",
            model_settings=ModelSettings(
                tool_choice="auto",
                parallel_tool_calls=True,
                truncation="auto",
                temperature=0.2,  # 결정적 응답으로 속도 향상
                frequency_penalty=0.1,
                presence_penalty=0.1,
            ),
        )
        self.user_manager = UserManager()

    def set_default_openai_key(self):
        set_default_openai_key(os.getenv("OPENAI_API_KEY"), True)

    async def search_nearby_places(
        self, latitude: float, longitude: float
    ) -> List[dict]:
        """
        Google Places API를 사용해서 주변 장소를 검색합니다.
        """
        try:
            api_key = os.getenv("GOOGLE_PLACES_API_KEY")
            if not api_key:
                logger.error("GOOGLE_PLACES_API_KEY가 설정되지 않았습니다.")
                return []

            logger.info(f"Google Places API 키 확인: {api_key[:10]}...")

            url = "https://places.googleapis.com/v1/places:searchNearby"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.displayName,places.types,places.location",
            }

            payload = {
                "includedTypes": [
                    "restaurant",
                    "cafe",
                    "bar",
                    "hotel",
                    "museum",
                    "park",
                    "shopping_mall",
                    "zoo",
                    "library",
                    "hospital",
                    "school",
                    "university",
                    "bank",
                    "post_office",
                    "fire_station",
                ],
                "languageCode": "ko",
                "maxResultCount": 5,
                "locationRestriction": {
                    "circle": {
                        "center": {
                            "latitude": float(latitude),
                            "longitude": float(longitude),
                        },
                        "radius": 500.0,
                    }
                },
            }

            logger.info(f"Google Places API 요청: {url}")
            logger.info(f"요청 페이로드: {payload}")

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code != 200:
                    logger.error(f"Google Places API 오류: {response.status_code}")
                    logger.error(f"응답 내용: {response.text}")

                    if response.status_code == 403:
                        logger.error("403 Forbidden - API 키 확인 필요:")
                        logger.error("1. GOOGLE_PLACES_API_KEY 환경변수 확인")
                        logger.error(
                            "2. Google Cloud Console에서 Places API 활성화 확인"
                        )
                        logger.error("3. API 키에 Places API 권한 확인")
                        logger.error("4. API 키 할당량 확인")

                    return []

                data = response.json()
                places = data.get("places", [])
                logger.info(f"주변 장소 {len(places)}개 발견")
                return places

        except Exception as e:
            logger.error(f"Google Places API 호출 중 오류 발생: {str(e)}")
            return []

    async def create_agent_from_place(self, place: dict) -> AgentDTO:
        """
        장소 정보를 기반으로 Agent를 생성합니다.
        """
        logger.info(f"create_agent_from_place: {place}")
        try:
            display_name = place.get("displayName", {}).get("text", "알 수 없는 장소")
            location = place.get("location", {})
            place_types = place.get("types", [])

            # 장소 타입에 따른 프롬프트 생성
            type_prompt = ""
            for type_text in place_types:
                try:
                    type_prompt += self._generate_type_prompt(type_text)
                except Exception as e:
                    logger.error(f"장소 타입 프롬프트 생성 중 오류 발생: {str(e)}")
                    pass

            agent_id = str(uuid.uuid4())
            agent = AgentDTO(
                agent_id=agent_id,
                name=display_name,
                description=f"{display_name} 챗봇",
                prompt=f"""
                당신은 {display_name}의 챗봇입니다.
                {type_prompt}
                
                # 응답 스타일
                - 유머와 은유를 적극 활용하며, 필요하다면 가벼운 비속어("ㅋㅋ, ㅂㅅ, 어쩔? 등")을 사용하여 캐릭터의 개성을 강조합니다.
                - 해당 에이전트는 장소와 관련되어 있기 때문에, 해당 위치 기반으로 추가 정보와 응답 스타일을 자유롭게 이야기합니다.
                - 출력 토큰은 170 토큰 미만으로만 사용해야 합니다.
                """,
                latitude=float(location.get("latitude", 0)),
                longitude=float(location.get("longitude", 0)),
                thumbnail="",
                tools=[],
                model="gpt-4.1-mini",
                achievements=[],
            )

            return agent

        except Exception as e:
            logger.error(f"Agent 생성 중 오류 발생: {str(e)}")
            return None

    def _generate_type_prompt(self, place_types: List[str]) -> str:
        """
        장소 타입에 따른 프롬프트를 생성합니다.
        """
        type_prompts = {
            "restaurant": "맛집 정보, 추천 메뉴, 영업시간, 가격대 등을 알려주세요.",
            "cafe": "카페 분위기, 추천 음료, 디저트, 영업시간 등을 알려주세요.",
            "bar": "술집 분위기, 추천 술, 안주, 영업시간 등을 알려주세요.",
            "hotel": "호텔 시설, 객실 정보, 체크인/아웃 시간, 주변 관광지를 알려주세요.",
            "museum": "전시 정보, 관람 시간, 입장료, 특별 전시 등을 알려주세요.",
            "park": "공원 시설, 산책로, 휴식 공간, 계절별 볼거리를 알려주세요.",
            "shopping_mall": "쇼핑몰 매장, 영업시간, 주차 정보, 푸드코트 등을 알려주세요.",
            "zoo": "동물 정보, 관람 시간, 입장료, 특별 이벤트를 알려주세요.",
            "library": "도서관 시설, 대출 방법, 열람실, 특별 컬렉션을 알려주세요.",
            "hospital": "진료과목, 진료시간, 예약 방법, 응급실 정보를 알려주세요.",
            "school": "학교 정보, 교육 과정, 입학 안내, 시설을 알려주세요.",
            "university": "대학교 정보, 학과, 입학 안내, 캠퍼스 시설을 알려주세요.",
            "bank": "은행 서비스, 영업시간, ATM 위치, 대출 상품을 알려주세요.",
            "post_office": "우체국 서비스, 영업시간, 택배 서비스, 우표 구매를 알려주세요.",
            "fire_station": "소방서 정보, 화재 예방, 응급 상황 대처법을 알려주세요.",
        }

        for place_type in place_types:
            if place_type in type_prompts:
                return type_prompts[place_type]

        return "해당 장소에 대한 정보를 제공해주세요."

    async def create_agents_from_nearby_places(
        self, latitude: float, longitude: float
    ) -> List[AgentDTO]:
        """
        주변 장소를 검색하고 Agent를 생성하여 데이터베이스에 저장합니다.
        """
        try:
            places = await self.search_nearby_places(latitude, longitude)
            if not places:
                logger.warning("주변 장소를 찾을 수 없습니다.")
                return []

            created_agents = []
            for place in places:
                agent = await self.create_agent_from_place(place)
                if agent:
                    await self.register_agent(agent)
                    created_agents.append(agent)
                    logger.info(f"Agent 생성 완료: {agent.name}")

            return created_agents

        except Exception as e:
            logger.error(f"주변 장소 기반 Agent 생성 중 오류 발생: {str(e)}")
            return []

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
                raise Exception(f"에이전트를 찾을 수 없습니다: {agent_id}")
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
        데이터가 없을 경우 Google Places API를 통해 주변 장소를 찾아 Agent를 생성합니다.
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
                if not items:
                    # 데이터가 없을 경우 Google Places API를 통해 주변 장소를 찾아 Agent 생성
                    logger.info(
                        "주변 Agent가 없습니다. Google Places API를 통해 새로운 Agent를 생성합니다."
                    )
                    created_agents = await self.create_agents_from_nearby_places(
                        latitude, longitude
                    )
                    logger.info(f"created_agents: {created_agents}")
                    return created_agents

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
            return agent

    async def delete_agent(self, agent_id: str):
        # 에이전트 존재 여부 확인
        agent = await self.get_agent(agent_id)
        if agent is None:
            raise Exception(f"에이전트를 찾을 수 없습니다: {agent_id}")

        # 에이전트 삭제
        async with self.session.resource(
            "dynamodb", region_name=self.region_name
        ) as dynamodb:
            table = await dynamodb.Table(self.table_name)
            await table.delete_item(Key={"agent_id": agent_id})
            return {"message": "Agent deleted successfully"}

    # Agent DTO 기반으로 에이전트 만들어야함
    async def load_agent(self, agent_id: str):
        # 에이전트 정보 로드
        agent_dto = await self.get_agent(agent_id)
        if agent_dto is None:
            raise Exception(f"에이전트를 찾을 수 없습니다: {agent_id}")

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
        # 에이전트 존재 여부 확인
        agent = await self.get_agent(agent_id)
        if agent is None:
            raise Exception(f"에이전트를 찾을 수 없습니다: {agent_id}")

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

    async def get_chat_list(self, sub: str) -> List[ChatListDTO]:
        """
        특정 사용자의 챗봇과의 대화 내역을 조회합니다.
        특정 챗봇과의 대화를 진행한 경우에만 필터링 되어 조회
        agent_id 기준으로 중복 없이 조회
        :param sub: 사용자 식별자
        :return: 시간순으로 정렬된 ChatListDTO 리스트
        """
        try:
            # 에이전트 네이밍을 미리 모두 받아오기
            agents = await self.list_agents()
            agent_names = {agent.agent_id: agent.name for agent in agents}

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
                            ChatListDTO(
                                agent_id=latest_item["agent_id"],
                                name=agent_names[latest_item["agent_id"]],
                                content=latest_item["content"],
                                timestamp=latest_item["timestamp"],
                            )
                        )
                # latest_chats 정렬 최신 시간순으로
                latest_chats.sort(key=lambda x: x.timestamp, reverse=True)
                return latest_chats
        except Exception as e:
            logger.error(f"채팅 히스토리 조회 중 오류 발생: {str(e)}")
            return []

    async def delete_agent_history(
        self, sub: str, agent_id: str
    ) -> List[ChatMessageDTO]:
        # 에이전트 존재 여부 확인
        agent = await self.get_agent(agent_id)
        if agent is None:
            raise Exception(f"에이전트를 찾을 수 없습니다: {agent_id}")

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
                    raise Exception(f"에이전트를 찾을 수 없습니다: {agent_id}")

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
            raise e

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
                    raise Exception(f"에이전트를 찾을 수 없습니다: {agent_id}")

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
            logger.error(f"에이전트 업적 추가 중 오류 발생: {str(e)}")
            raise e

    async def add_achievement_to_user(
        self, sub: str, agent_id: str, achievement_list: List[AchievementDTO]
    ):
        """
        사용자의 업적 리스트에 추가합니다.
        :param sub: 사용자 식별자
        :param agent_id: 에이전트 ID
        :param achievement_list: 추가할 업적 리스트
        """
        try:
            async with self.session.resource(
                "dynamodb", region_name=self.region_name
            ) as dynamodb:
                table = await dynamodb.Table(self.user_achievement_table_name)

                # 이미 달성한 업적 조회
                response = await table.scan(
                    FilterExpression="#sub_agent_id = :sub_agent_id",
                    ExpressionAttributeNames={"#sub_agent_id": "sub#agent_id"},
                    ExpressionAttributeValues={":sub_agent_id": f"{sub}#{agent_id}"},
                    ProjectionExpression="id",
                )
                existing_achievements = {
                    item["id"] for item in response.get("Items", [])
                }

                # 새로운 업적만 필터링
                new_achievements = [
                    achievement
                    for achievement in achievement_list
                    if achievement.id not in existing_achievements
                ]

                if not new_achievements:
                    logger.info(f"사용자 {sub}가 이미 모든 업적을 달성했습니다.")
                    return

                # 새로운 업적만 추가
                for achievement in new_achievements:
                    await table.put_item(
                        Item={
                            "pk": str(uuid.uuid4()),  # 유니크한 파티션 키
                            "sub#agent_id": f"{sub}#{agent_id}",  # 정렬 키
                            "sub": sub,
                            "agent_id": agent_id,
                            "id": achievement.id,
                            "name": achievement.name,
                            "description": achievement.description,
                            "condition": achievement.condition,
                            "image": achievement.image,
                            "rarity": achievement.rarity,
                            "timestamp": datetime.datetime.now().isoformat(),
                        }
                    )
                    logger.info(
                        f"사용자 {sub}의 새로운 업적 '{achievement.name}' 추가 완료"
                    )
                    # TODO: Web Push 아밴트 추가
                    # 웹 푸시 전송
                    push_endpoint = Request.url_for("user_push", sub=sub)
                    if push_endpoint:
                        push_payload = {
                            "achievement": achievement.name,
                            "rarity": achievement.rarity,
                        }
                        await self.user_manager.send_web_push(
                            push_endpoint, push_payload
                        )

        except Exception as e:
            logger.error(f"사용자 업적 추가 중 오류 발생: {str(e)}")
            return None
