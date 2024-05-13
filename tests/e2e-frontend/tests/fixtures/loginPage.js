export class LoginPage {
  /**
   * @param {import('@playwright/test').Page} page
   * @param {string} productUrl
   */
  constructor(page, productUrl) {
    this.page = page;
    this.productUrl = productUrl;
  }

  async goto() {
    await this.page.goto(this.productUrl);
  }

  /**
   * @param {string} email
   * @param {string} password
   */
  async login(email, password) {
    const usernameField = this.page.getByTestId("loginUserEmailFld");
    const passwordField = this.page.getByTestId("loginPasswordFld");
    const submitButton = this.page.getByTestId("loginSubmitBtn");

    await usernameField.fill(email);
    await passwordField.fill(password);
    await submitButton.click();
  }

  async logout() {
    const navUserMenuButton = this.page.getByTestId("userMenuBtn");
    await navUserMenuButton.click();

    const navLogoutButton = this.page.getByTestId("userMenuLogoutBtn");
    await navLogoutButton.click();
  }
}
