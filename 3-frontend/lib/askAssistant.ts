export function buildAskAssistantRequest(message: string, sessionId?: string) {
  return {
    data: "overall",
    message,
    session_id: sessionId,
  };
}
