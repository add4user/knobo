export const ChatState = {
  OPEN: "OPEN",
  CLOSED: "CLOSED",
};

/**
 * Service to manage chat state data and fetch data from server.
 * Will be moved to separate codebase once it is tested.
 */
export class ChatService {
  constructor() {
    this.chatState = ChatState.CLOSED;
  }

  /**
   * Toggle Chat State and return the new state.
   */
  toggleState() {
    if (this.chatState === ChatState.CLOSED) {
      this.chatState = ChatState.OPEN;
    } else {
      this.chatState = ChatState.CLOSED;
    }
    return this.chatState;
  }
}
