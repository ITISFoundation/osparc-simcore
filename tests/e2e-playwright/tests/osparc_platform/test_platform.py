# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=no-name-in-module

# import logging
# import re
# from collections.abc import Callable, Iterator

# import pytest
# from playwright.sync_api import BrowserContext, Page, WebSocket
# from pydantic import AnyUrl
# from pytest_simcore.helpers.logging_tools import log_context
# from pytest_simcore.helpers.playwright import (
#     AutoRegisteredUser,
#     web_socket_default_log_handler,
# )
# from pytest_simcore.helpers.pydantic_extension import Secret4TestsStr


# @pytest.fixture
# def log_in_and_out(
#     page: Page,
#     product_url: AnyUrl,
#     user_name: str,
#     user_password: Secret4TestsStr,
#     auto_register: bool,
#     register: Callable[[], AutoRegisteredUser],
#     context: BrowserContext,
# ) -> Iterator[WebSocket]:
#     with log_context(
#         logging.INFO,
#         f"Open {product_url=} using {user_name=}/{user_password=}/{auto_register=}",
#     ):
#         response = page.goto(f"{product_url}")
#         assert response
#         assert response.ok, response.body()

#     # In case the accept cookies or new release window shows up, we accept
#     page.wait_for_timeout(2000)
#     acceptCookiesBtnLocator = page.get_by_test_id("acceptCookiesBtn")
#     if acceptCookiesBtnLocator.is_visible():
#         acceptCookiesBtnLocator.click()
#         page.wait_for_timeout(1000)
#         newReleaseCloseBtnLocator = page.get_by_test_id("newReleaseCloseBtn")
#         if newReleaseCloseBtnLocator.is_visible():
#             newReleaseCloseBtnLocator.click()

#     with (
#         log_context(
#             logging.INFO,
#             f"Log in {product_url} using {user_name=}/{user_password=}/{auto_register=}",
#         ),
#         page.expect_websocket() as ws_info,
#     ):
#         if auto_register:
#             register()
#         else:
#             with log_context(
#                 logging.INFO,
#                 f"Log in {product_url=} using {user_name=}/{user_password=}",
#             ):
#                 _user_email_box = page.get_by_test_id("loginUserEmailFld")
#                 _user_email_box.click()
#                 _user_email_box.fill(user_name)
#                 _user_password_box = page.get_by_test_id("loginPasswordFld")
#                 _user_password_box.click()
#                 _user_password_box.fill(user_password.get_secret_value())
#                 with page.expect_response(re.compile(r"/login")) as response_info:
#                     page.get_by_test_id("loginSubmitBtn").click()
#                 assert response_info.value.ok, f"{response_info.value.json()}"

#     assert not ws_info.value.is_closed()


#     # Welcome to Sim4Life
#     page.wait_for_timeout(5000)
#     welcomeToSim4LifeLocator = page.get_by_text("Welcome to Sim4Life")
#     if welcomeToSim4LifeLocator.is_visible():
#         page.get_by_text("").nth(
#             1
#         ).click()  # There is missing osparc-test-id for this button
#     # Quick start window
#     quickStartWindowCloseBtnLocator = page.get_by_test_id("quickStartWindowCloseBtn")
#     if quickStartWindowCloseBtnLocator.is_visible():
#         quickStartWindowCloseBtnLocator.click()

#     context.storage_state(path="state.json")

#     yield ws

#     with log_context(
#         logging.INFO,
#         f"Log out of {product_url=} using {user_name=}/{user_password=}",
#     ):
#         page.keyboard.press("Escape")
#         page.get_by_test_id("userMenuBtn").click()
#         with page.expect_response(re.compile(r"/auth/logout")) as response_info:
#             page.get_by_test_id("userMenuLogoutBtn").click()
#         assert response_info.value.ok, f"{response_info.value.json()}"
#         # so we see the logout page
#         page.wait_for_timeout(500)


# @pytest.fixture
# def logged_in_context(playwright):
#     browser = playwright.chromium.launch(headless=False)
#     context = browser.new_context(storage_state="state.json")
#     yield context
#     context.close()
#     browser.close()


# def test_simple_folder_workflow(logged_in_context, product_url):
#     page = logged_in_context.new_page()

#     page.goto(f"{product_url}")
#     page.wait_for_timeout(1000)
#     page.get_by_test_id("dashboard").get_by_text("New folder", exact=True).click()
#     page.get_by_placeholder("Title").fill("My new folder")
#     page.get_by_placeholder("Title").press("Enter")

#     page.get_by_test_id("dashboard").get_by_text("My new folder").click()
#     page.get_by_test_id("contextTree").get_by_text("My Workspace").click()


# def test_simple_workspace_workflow(logged_in_context, product_url):
#     page = logged_in_context.new_page()

#     page.goto(f"{product_url}")
#     page.wait_for_timeout(1000)
#     page.get_by_test_id("userMenuBtn").click()
#     page.wait_for_timeout(1000)
