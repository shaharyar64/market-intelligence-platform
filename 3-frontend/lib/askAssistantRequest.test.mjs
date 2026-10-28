import test from "node:test";
import assert from "node:assert/strict";
import { buildAskAssistantRequest } from "./askAssistant.ts";

test("Ask Analytics Platform sends arbitrary dashboard questions in overall mode", () => {
  assert.deepEqual(buildAskAssistantRequest("Which bank posted more?", "session-1"), {
    data: "overall",
    message: "Which bank posted more?",
    session_id: "session-1",
  });
});
