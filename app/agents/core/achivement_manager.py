# 업적 처리를 위한 클래스

import logging
from typing import List

from boto3.dynamodb.conditions import Key
from litellm import BaseModel

from agents import Agent, RunConfig, Runner, WebSearchTool
from app.agents.core.agent_manager import AgentManager, DynamoDBManager
from app.agents.schemas.achivement_schemas import (
    AchievementDTO,
    AchievementGeneratorOutput,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

manager = AgentManager()


class OutlineCheckerOutput(BaseModel):
    more: bool
    sufficient: bool


# 다이나모 DB 연결 클래스 상속
class AgentAchievements(DynamoDBManager):
    def __init__(self):
        super().__init__()
        self.tester = Agent[None](
            name="ChatTester",
            instructions="""
            당신의 역할은 '실제 사용자'로 다양한 챗봇들과 상호작용을 통해 대화를 지속해야합니다.

            '실제 사용자'의 페르소나를 설정해서 대화를 해야합니다.
            페르소나는 다음과 같이 설정합니다.
            - 이름: 사용자의 이름(한국인)
            - 나이: 사용자의 나이(30대 초반 ~ 40대 초반)
            - 성별: 사용자의 성별(남자, 여자)
            - 직업: 사용자의 직업(회사원, 학생, 자영업 등)
            - MBTI: 사용자의 MBTI(ISTJ, ISFJ, INFJ, INTJ, ISTP, ISFP, INFP, INTP)
            - 컨셉: 병맛, 욕쟁이, 일반인, 잦은 야근, 인터넷 커뮤니티 중독, 주갤러 등

            정직한 느낌이 아닌, 약간 MZ 감성을 섞어야 하고, SNL 및 유튜브, 커뮤니티 컨셉을 섞어야 합니다.
            페르소나 기반으로 특정 챗봇과 대화를 하기 위한 내용만 작성합니다.

            * 약간의 비속어, 꼰대 기질, MZ 스타일, 병맛 스타일을 반드시 섞어야 합니다.
            * 반드시 용어와 단어는 웹검색 기반으로 찾은 최신 MZ 감성과 용어, 단어, 컨셉을 유지해야합니다.
            """,
            model="gpt-4o-mini",
            tools=[WebSearchTool()],
        )

        self.evaluator = Agent[None](
            name="AchievementEvaluator",
            instructions="""
            당신은 특정 역할을 하는 챗봇의 업적 시스템을 구축하기 위해 대화 내용을 분석하고 평가하는 평가자 입니다.
            주어진 대화 정보만을 토대로 반드시 게임 서비스에서 챗봇 대화 업적을 만들어야하기 때문에, 충분한 대화가 이어졌는지 평가합니다. 

            주어진 대화를 통해 판단하기 위한 기준은 다음과 같습니다.
            1. 단순 정보 공유 내용이 아닌, 재미와 흥미 위주의 대화가 이어가야합니다.
            2. 최소한 대화는 8회 미만인 경우, 충분하지 않다고 판단해야합니다.
            3. 대화의 퀄리티가 낮거나, 반복된 내용이 이어지는 것은 충분하지 않다고 판단해야합니다.
            4. 대화는 기승전결이 완벽한 구성으로 끝나야해. 중간에 끝나거나 그러면 충분하지 않다고 판단해야해.

            충분하다 판단되면, "sufficient"
            부족하다 판단되면, "more"
            """,
            model="gpt-4.1-mini",
            output_type=OutlineCheckerOutput,
        )

        self.achievement_generator = Agent[None](
            name="AchievementGenerator",
            instructions="""
            업적은 다음과 같이 4가지 분류로 나뉩니다.
            1. Common(50%): 일반적인 업적으로 쉽게 얻을 수 있는 업적입니다.
            2. Rare(30%): 조금 어려운 업적으로 조금 더 노력을 해야 얻을 수 있는 업적입니다.
            3. Epic(15%): 매우 어려운 업적으로 매우 노력을 해야 얻을 수 있는 업적입니다.
            4. Legendary(5%): 매우 매우 어려운 업적으로 매우 매우 노력을 해야 얻을 수 있는 업적입니다.

            전달받은 대화 내용을 토대로 업적 리스트를 만들어야합니다.
            업적 정보는 다음과 같이 구성됩니다.
            - 업적 아이디(id): uuid 형식
            - 업적 이름(name): 업적 이름
            - 업적 설명(description): 업적 설명
            - 업적 이미지(image): 업적 이미지 설명(생성형 AI를 통해 업적 이미지를 만들 예정이므로 프롬프트 내용을 최대한 자세히 작성해야합니다.)
            - 업적 등급(rarity): 업적 등급(Common, Rare, Epic, Legendary)
            - 업적 조건(condition): 업적 조건(대화 내용, 흐름, 페르소나 정보 기반으로 업적 조건을 작성해야합니다.)

            # 업적 생성을 위한 요소
            * 업적을 통해 실제 App 서비스에 보여져야 하기 때문에, 재미와 흥미 위주로 만들어야해.
            * 단순한 정보 전달이 아닌, 재미와 흥미 위주로 만들어야해.
            * 업적의 느낌은 유튜브 B 급 감성을 추구해야해.
            * 약간 병맛 느낌도 좋아.
            * 업적은 챗봇의 성격을 대변해야해. 단순 해당 챗봇의 정보가 아닌 성격을 대변하는 느낌이어야해.


            최소 10개의 업적 리스트를 만들어야하고, 업적 분류 퍼센트에 맞춰서 만들어야합니다.
            최소한 각 분류 등급 별로 업적 1개씩은 만들어야합니다.
            """,
            model="gpt-4o-mini",
            output_type=AchievementGeneratorOutput,
        )

    async def generate_chat_and_achievements(
        self, agent_id: str
    ) -> AchievementGeneratorOutput:
        """
        Agent 아이디를 기반으로 챗봇과 대화를 하며 업적 리스트를 생성합니다.
        :param agent_id: Agent 아이디
        """
        chat_init = False
        formatted_history = []
        while True:
            agent_dto = await manager.get_agent(agent_id)
            agent = await manager.load_agent(agent_id)
            if not chat_init:
                logger.info(f"[{agent.name}] 챗봇과 이야기를 시작합니다.")
                init_test = await Runner.run(
                    self.tester,
                    input=f"""다음 챗봇과 이야기를 하게 됩니다. 챗봇의 정보는 다음과 같습니다.
                    {agent_dto.model_dump_json()}

                    # 위 정보와 히스토리를 기반으로 다음 대화를 이어나가야합니다.
                    이어나가기 위한 대화 내용을 작성합니다. 처음 대화는 챗봇의 정보를 너의 페르소나로 대화를 시작해야합니다.
                    """,
                    run_config=RunConfig(
                        tracing_disabled=True,
                    ),
                )
                chat_init = True
                logger.info(f"[User] {init_test.final_output}")
                formatted_history.append(
                    {"role": "user", "content": init_test.final_output}
                )
            else:
                continue_test = await Runner.run(
                    self.tester,
                    input=f"""다음 챗봇과 이야기를 하게 됩니다. 챗봇의 정보는 다음과 같습니다.
                    {agent_dto.model_dump_json()}

                    # 채팅 히스토리
                    {formatted_history}

                    # 위 정보와 히스토리를 기반으로 다음 대화를 이어나가야합니다.
                    이어나가기 위한 대화 내용을 작성합니다.
                    """,
                    run_config=RunConfig(
                        tracing_disabled=True,
                    ),
                )
                logger.info(f"[User] {continue_test.final_output}")
                formatted_history.append(
                    {"role": "user", "content": continue_test.final_output}
                )

            result = await Runner.run(
                agent,
                input=formatted_history,
                run_config=RunConfig(
                    tracing_disabled=True,
                ),
            )
            logger.info(f"[{agent.name}] {result.final_output}")
            formatted_history.append(
                {"role": "assistant", "content": result.final_output}
            )

            judgement = await Runner.run(
                self.evaluator,
                input=formatted_history,
                run_config=RunConfig(
                    tracing_disabled=True,
                ),
            )

            if judgement.final_output.sufficient:
                achievement_generator_input = await Runner.run(
                    self.achievement_generator,
                    input=formatted_history,
                    run_config=RunConfig(
                        tracing_disabled=True,
                    ),
                )
                break
        logger.info(f"[{agent.name}] 업적 생성 완료")

        # AchievementGeneratorOutput 형식으로 변환하여 반환
        return AchievementGeneratorOutput(
            chat_history=achievement_generator_input.final_output.chat_history,
            achievements=achievement_generator_input.final_output.achievements,
        )

    async def get_list_agent_achievements(self, agent_id: str) -> List[AchievementDTO]:
        """
        Agent 아이디를 기반으로 업적 리스트를 조회합니다.
        :param agent_id: Agent 아이디
        :return: 해당 에이전트 챗봇에서 얻을 수 있는 업적 리스트 전체 반환
        """
        async with self.session.resource(
            "dynamodb", region_name=self.region_name
        ) as dynamodb:
            table = await dynamodb.Table(self.achievement_table_name)
            response = await table.query(
                KeyConditionExpression=Key("agent_id").eq(agent_id)
            )
            return [AchievementDTO(**item) for item in response.get("Items", [])]

    async def get_list_user_achievements(self, sub: str) -> List[AchievementDTO]:
        """
        User 아이디를 기반으로 업적 리스트를 조회합니다.
        :param sub: User 아이디
        :return: 해당 사용자가 얻은 업적 리스트 전체 반환
        """
        async with self.session.resource(
            "dynamodb", region_name=self.region_name
        ) as dynamodb:
            table = await dynamodb.Table(self.achievement_table_name)
            response = await table.query(KeyConditionExpression=Key("user_id").eq(sub))
            return [AchievementDTO(**item) for item in response.get("Items", [])]
