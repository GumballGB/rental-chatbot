# Inspired by Mockito, this file provides a simple fake for the Anthropic client 
# that can be used in tests. It allows you to script responses and track calls made to the client.

# fast way to make objects with attributes, like the real Anthropic responses
from types import SimpleNamespace

# Production code uses the Anthropic client to interact with the model.
# It expects the client, client.messages and client.messages.create to 
# behave in a certain way. This fake mimics that behavior for testing purposes.

# This builds a fake response
def text_response(text: str, *, stop_reason: str = "end_turn", input_tokens: int = 0, output_tokens: int = 0):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )

# Fakes a tool use response
def tool_use_response(tool_name: str, tool_input: dict, *, tool_use_id: str = "toolu_1"):
    return SimpleNamespace(
        stop_reason="tool_use",
        content=[
            SimpleNamespace(
                type="tool_use",
                name=tool_name,
                input=tool_input,
                id=tool_use_id,
            )
        ],
        usage=SimpleNamespace(input_tokens=0, output_tokens=0),
    )

# Similar to the real Anthropic client, this fake client has a messages attribute 
# that can be used to create messages and get scripted responses.
# Same as client.messages.create, it takes the same arguments and returns a scripted response.
class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self._index = 0

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._index >= len(self._responses):
            raise RuntimeError("FakeMessages has no scripted response left.")
        response = self._responses[self._index]
        self._index += 1
        return response

# Similar to the real Anthropic client, this fake client has a messages attribute
class FakeAnthropicClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)
