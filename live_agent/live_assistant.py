from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

class AssistantLive:
    def __init__(self, car, client=None):
        self.car = car
        self.client = client or genai.Client(http_options={"api_version": "v1alpha"})
        self.model_id = "gemini-3.8-live"

    def get_tools_mapping(self):
        car = self.car
        # W trybie Live funkcje mapuje się bezpośrednio lub przekazuje jako callable do SDK
        return {
            "play_pause": car.music.play_pause,
            "next_track": car.music.next_track,
            "previous_track": car.music.previous_track,
            "call_contact": car.contacts.call_contact,
            "navigate_to": car.set_destination,
            "save_address": car.save_address,
        }

    def get_function_declarations(self):
        """Returns the tool schemas exposed to Gemini Live."""
        return [
            types.FunctionDeclaration(
                name="play_pause",
                description="Włącza lub pauzuje muzykę.",
            ),
            types.FunctionDeclaration(
                name="next_track",
                description="Przełącza na następny utwór.",
            ),
            types.FunctionDeclaration(
                name="previous_track",
                description="Przełącza na poprzedni utwór.",
            ),
            types.FunctionDeclaration(
                name="call_contact",
                description="Dzwoni do kontaktu.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "name": types.Schema(type=types.Type.STRING),
                        "number_type": types.Schema(type=types.Type.STRING),
                    },
                    required=["name"],
                ),
            ),
            types.FunctionDeclaration(
                name="navigate_to",
                description="Ustawia cel nawigacji.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={"address": types.Schema(type=types.Type.STRING)},
                    required=["address"],
                ),
            ),
            types.FunctionDeclaration(
                name="save_address",
                description="Zapisuje adres pod etykietą.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "label": types.Schema(type=types.Type.STRING),
                        "address": types.Schema(type=types.Type.STRING),
                    },
                    required=["label", "address"],
                ),
            ),
        ]

    def execute_tool_call(self, function_call):
        """Execute one Live API function call and build its response."""
        tool_func = self.get_tools_mapping().get(function_call.name)
        if tool_func is None:
            result = f"Nie znaleziono funkcji: {function_call.name}"
        else:
            result = tool_func(**(function_call.args or {}))

        return types.FunctionResponse(
            name=function_call.name,
            id=function_call.id,
            response={"result": result},
        )

    def get_function_responses(self, tool_call):
        """Convert a Live API tool call into responses, including an empty call."""
        return [
            self.execute_tool_call(function_call)
            for function_call in (tool_call.function_calls or [])
        ]

    def get_config(self):
        return types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
            tools=[types.Tool(function_declarations=self.get_function_declarations())],
        )

    async def start_live_session(self):
        """Uruchamia sesję Live przez WebSocket z obsługą tool calls i audio."""
        async with self.client.aio.live.connect(
            model=self.model_id, config=self.get_config()
        ) as session:
            print("Połączono z Gemini Live API!")

            while True:
                async for response in session.receive():
                    if response.tool_call:
                        responses = self.get_function_responses(response.tool_call)
                        if responses:
                            await session.send_tool_response(function_responses=responses)
