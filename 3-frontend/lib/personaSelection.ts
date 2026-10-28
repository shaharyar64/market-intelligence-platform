export class PersonaSaveQueue {
  private tail: Promise<void> = Promise.resolve();

  enqueue(save: () => Promise<void>): Promise<void> {
    const current = this.tail.then(save, save);
    this.tail = current;
    return current;
  }
}

export function assertPersonaSaveResponse(
  response: Pick<Response, "ok" | "status">,
): void {
  if (!response.ok) {
    throw new Error(`Could not save persona (${response.status})`);
  }
}
