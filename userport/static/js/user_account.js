export class UserAccount {
  constructor() {
    this.userAccountContainer = document.querySelector("#user-account");
    this.userAccountContainer.addEventListener(
      "click",
      this.handleUserAccountClick.bind(this)
    );
    this.dropDownContent = document.querySelector(
      ".user-account-dropdown-content"
    );
  }

  handleUserAccountClick(event) {
    this.dropDownContent.classList.toggle("show");
  }
}
