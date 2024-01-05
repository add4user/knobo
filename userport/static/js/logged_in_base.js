import { ChatService, ChatState } from "./chat_service.js";

export class LoggedInBaseView {
  /**
   * Contains logic associated with the common logged in view of the user.
   */
  constructor() {
    this.userAccountContainer = document.querySelector("#user-account");
    this.userAccountContainer.addEventListener(
      "click",
      this.handleUserAccountClick.bind(this)
    );
    this.dropDownContent = document.querySelector(
      ".user-account-dropdown-content"
    );

    // Assign event listeners to all list elements.
    document.querySelectorAll("#left-nav li a").forEach((a) => {
      if (a.hasAttribute("href") && a.href == window.location.href) {
        a.classList.add("active");
      }
    });

    // Temporary code which will be moved to separate codebase after testing.
    this.chatBtn = document.querySelector("#userport-widget-btn");
    this.chatContainer = document.querySelector("#userport-chat-container");
    this.chatBtn.addEventListener(
      "click",
      this.handleChatWidgetButtonClick.bind(this)
    );
    this.chatMessagesList = document.querySelector(
      "#userport-chat-messages-list"
    );
    this.chatMessageTextArea = document.querySelector(
      "#userport-query-textarea"
    );
    document
      .querySelector("#userport-query-btn")
      .addEventListener("click", this.handlePostChatMessage.bind(this));
    // Only for testing, never expose API key in code in prod.
    const apiKey = "hW0DOrPmyY9Pi5ADm0bugg";
    this.chatService = new ChatService(apiKey);

    this.chatService.addEventListener(
      "userport_post_message_start",
      this.handleMessagePostStart.bind(this)
    );

    this.chatService.addEventListener(
      "userport_post_message_end",
      this.handleMessagePostEnd.bind(this)
    );
  }

  /**
   * Show or hide dropdown on user click.
   * @param {Event} event
   */
  handleUserAccountClick(event) {
    this.dropDownContent.classList.toggle("show");
  }

  /**
   * Temporary section below which will be moved to separate codebase after testing.
   */

  // Handle Chat widget button click.
  handleChatWidgetButtonClick() {
    const chatState = this.chatService.toggleState();
    if (chatState === ChatState.OPEN) {
      this.chatBtn.innerText = "X";
    } else {
      this.chatBtn.innerText = "Ask AI";
    }
    this.chatContainer.classList.toggle("userport-hidden");
  }

  // Handle message post on send button click.
  handlePostChatMessage() {
    const postedMessage = this.chatMessageTextArea.value;
    this.chatService.postMessage(postedMessage);
    this.clearChatTextArea();
  }

  /**
   * Update view when message posted has started.
   */
  handleMessagePostStart() {
    this.renderChatMessages(true);
  }

  /**
   * Update view when message posted has completed.
   */
  handleMessagePostEnd() {
    this.renderChatMessages(false);
  }

  /**
   * Renders all chat messages in the view.
   */
  renderChatMessages(messagePostStart) {
    const chatMessages = this.chatService.getChatMessages();
    var chatMessagesNodeList = [];
    for (let i = 0; i < chatMessages.length; i++) {
      const chatMessage = chatMessages[i];
      const li = this.createChatMessage(chatMessage);
      chatMessagesNodeList.push(li);
    }
    if (messagePostStart) {
      // Add typing indicator to show user response is pending.
      chatMessagesNodeList.push(this.createTypingIndicator());
    }
    this.chatMessagesList.replaceChildren(...chatMessagesNodeList);
  }

  /**
   * Creates chat message and returns it as a HTMLElement.
   */
  createChatMessage(chatMessage) {
    let li = document.createElement("li");
    const is_human_message =
      chatMessage.message_creator_type === "HUMAN" ? true : false;

    li.classList.add("userport-message-common-container");
    if (is_human_message) {
      li.classList.add("userport-human-container");
    } else {
      li.classList.add("userport-bot-container");
    }

    let pHeader = document.createElement("p");
    pHeader.innerText = is_human_message ? "You" : "AI";
    pHeader.classList.add("userport-message-common-header");
    li.appendChild(pHeader);

    let pMessage = document.createElement("p");
    pMessage.classList.add("userport-common-message");
    if (is_human_message) {
      pMessage.classList.add("userport-human-message");
    } else {
      pMessage.classList.add("userport-bot-message");
    }
    pMessage.innerText = chatMessage.text;
    li.appendChild(pMessage);

    let pFooter = document.createElement("p");
    pFooter.classList.add("userport-common-message-footer");
    pFooter.innerText = chatMessage.created;
    li.appendChild(pFooter);

    return li;
  }

  /**
   * Clears chat text area after successful message post.
   */
  clearChatTextArea() {
    this.chatMessageTextArea.value = "";
  }

  /**
   * Create and return typing indicator HTML Element.
   */
  createTypingIndicator() {
    let div = document.createElement("div");
    div.classList.add("userport-typing-indicator");
    for (let i = 0; i < 3; i++) {
      let span = document.createElement("span");
      div.appendChild(span);
    }
    return div;
  }
}
