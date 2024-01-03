export const ChatState = {
  OPEN: "OPEN",
  CLOSED: "CLOSED",
};

/**
 * Service to manage chat state data and fetch data from server.
 * Will be moved to separate codebase once it is tested.
 */
export class ChatService extends EventTarget {
  constructor(apiKey) {
    super();
    this.apiKey = apiKey;
    this.chatState = ChatState.CLOSED;
    this.chatMessages = [];

    // Constants.
    this.INFERENCE_ENDPOINT = "/api/v1/inference";
    this.PROTOCOL_PREFIX = "http://";
    this.JSON_HTTP_HEADER_VALUE = "application/json";
    this.HTTP_POST_METHOD = "POST";
  }

  /**
   * Fetch chat messages
   * @returns Chat Messages.
   */
  getChatMessages() {
    return this.chatMessages;
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

  /**
   * Post a message to the server.
   */
  postMessage(user_query) {
    const user_query_message = {
      user_query: user_query,
    };

    // TODO: This endpoint should be different in prod i.e. it cannot be window.location.host.
    let endpoint_url = `${this.PROTOCOL_PREFIX}${window.location.host}${this.INFERENCE_ENDPOINT}`;

    // Push human message first. This should be replaced by server message instead.
    this.chatMessages.push({
      text: user_query,
      message_creator_type: "HUMAN",
      created: null,
    });
    this.dispatch_start_event();
    return fetch(endpoint_url, {
      method: this.HTTP_POST_METHOD,
      headers: {
        "Content-Type": this.JSON_HTTP_HEADER_VALUE,
        "X-API-KEY": this.apiKey,
      },
      body: JSON.stringify(user_query_message),
    })
      .then((response) =>
        response.json().catch((error) => {
          // Server returned a non JSON response.
          throw new Error(`${response.status}: Server error`);
        })
      )
      .then((data) => {
        // TODO: This is manual for now. Replace with server event.
        this.chatMessages[this.chatMessages.length - 1].created = "Test";
        // TODO: Add error code check and validate message before adding to message list.
        this.chatMessages.push(data);

        this.dispatch_end_event();
      })
      .catch((error) => {
        // Pop the last chat messages since it encounterted an error while being sent.
        this.chatMessages.pop();
        this.dispatch_end_event();
        throw error;
      });
  }

  /**
   * Helper to dispatch userport_post_message_start event.
   */
  dispatch_start_event() {
    this.dispatchEvent(new Event("userport_post_message_start"));
  }

  /**
   * Helper to dispatch userport_post_message_end event.
   */
  dispatch_end_event() {
    this.dispatchEvent(new Event("userport_post_message_end"));
  }
}
