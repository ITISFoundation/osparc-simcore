/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.support.SupportCenter", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "support-center");

    this.getChildControl("title").set({
      textAlign: "center",
    });

    this.set({
      layout: new qx.ui.layout.VBox(10),
      width: osparc.support.SupportCenter.WINDOW_WIDTH,
      height: osparc.support.SupportCenter.getMaxHeight(),
      modal: false,
      showMaximize: false,
      showMinimize: false,
      showClose: true,
    });

    this.getLayout().set({
      separator: "separator-vertical"
    });

    this.getChildControl("home-page");
    this.getChildControl("conversations-page");
    this.getChildControl("conversation-page");
    this.getChildControl("home-button");
    this.getChildControl("conversations-button");

    this.__showHome();
  },

  statics: {
    WINDOW_WIDTH: 430,
    WINDOW_HEIGHT: 700,
    REQUEST_CALL_MESSAGE: "Dear Support,\nI would like to make an appointment for a support call.",

    getMaxHeight: function() {
      // height: max 80% of screen, or WINDOW_HEIGHTpx
      const clientHeight = document.documentElement.clientHeight;
      return Math.min(osparc.support.SupportCenter.WINDOW_HEIGHT, parseInt(clientHeight * 0.8));
    },

    openWindow: function(stackPage) {
      const supportCenterWindow = new osparc.support.SupportCenter();

      if (stackPage === "conversations") {
        supportCenterWindow.showConversations();
      }

      const positionWindow = () => {
        supportCenterWindow.set({
          height: osparc.support.SupportCenter.getMaxHeight(),
        });
        // bottom right
        const clientWidth = document.documentElement.clientWidth;
        const clientHeight = document.documentElement.clientHeight;
        const posX = clientWidth - osparc.support.SupportCenter.WINDOW_WIDTH - 4;
        const posY = clientHeight - supportCenterWindow.getHeight() - 4;
        supportCenterWindow.moveTo(posX, posY);
      };
      supportCenterWindow.open();
      positionWindow();
      window.addEventListener("resize", positionWindow);

      return supportCenterWindow;
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "main-stack":
          control = new qx.ui.container.Stack();
          this.add(control, {
            flex: 1
          });
          break;
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignX: "center",
          }));
          this.add(control);
          break;
        case "home-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Support"),
            icon: "@FontAwesome5Solid/question-circle/18",
            backgroundColor: "transparent",
            iconPosition: "top",
            allowGrowX: true,
            center: true,
          });
          control.addListener("execute", () => this.__showHome(), this);
          this.getChildControl("buttons-layout").add(control, { flex: 1 });
          break;
        case "conversations-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Conversations"),
            icon: "@FontAwesome5Solid/comments/18",
            backgroundColor: "transparent",
            iconPosition: "top",
            allowGrowX: true,
            center: true,
          });
          control.addListener("execute", () => this.showConversations(), this);
          this.getChildControl("buttons-layout").add(control, { flex: 1 });
          break;
        case "home-page":
          control = new osparc.support.HomePage();
          control.addListener("openConversation", () => this.openConversation(), this);
          this.getChildControl("main-stack").add(control);
          break;
        case "conversations-stack":
          control = new qx.ui.container.Stack();
          this.getChildControl("main-stack").add(control);
          break;
        case "conversations-page":
          control = new osparc.support.ConversationsPage();
          control.addListener("openConversation", e => {
            const conversationId = e.getData();
            this.openConversation(conversationId);
          }, this);
          control.addListener("createConversationBookCall", () => this.createConversationBookCall(), this);
          this.getChildControl("conversations-stack").add(control);
          break;
        case "conversation-page":
          control = new osparc.support.ConversationPage();
          control.addListener("showConversations", () => this.showConversations(), this);
          this.getChildControl("conversations-stack").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __showHome: function() {
      this.setCaption(this.tr("Support"));
      this.getChildControl("main-stack").setSelection([this.getChildControl("home-page")]);
      this.getChildControl("home-button").set({
        textColor: "strong-main",
      });
      this.getChildControl("conversations-button").set({
        textColor: "text",
      });
    },

    showConversations: function() {
      this.setCaption(this.tr("Conversations"));
      this.getChildControl("main-stack").setSelection([this.getChildControl("conversations-stack")]);
      this.getChildControl("home-button").set({
        textColor: "text",
      });
      this.getChildControl("conversations-button").set({
        textColor: "strong-main",
      });
      this.getChildControl("conversations-stack").setSelection([this.getChildControl("conversations-page")]);
    },

    __showConversation: function() {
      this.getChildControl("main-stack").setSelection([this.getChildControl("conversations-stack")]);
      this.getChildControl("home-button").set({
        textColor: "text",
      });
      this.getChildControl("conversations-button").set({
        textColor: "strong-main",
      });
      this.getChildControl("conversations-stack").setSelection([this.getChildControl("conversation-page")]);
    },

    openConversation: function(conversationId) {
      const conversationPage = this.getChildControl("conversation-page");
      if (conversationId) {
        osparc.store.ConversationsSupport.getInstance().getConversation(conversationId)
          .then(conversation => {
            conversationPage.setConversation(conversation);
            this.__showConversation();
          });
      } else {
        conversationPage.setConversation(null);
        this.__showConversation();
      }
    },

    createConversationBookCall: function() {
      const conversationPage = this.getChildControl("conversation-page");
      conversationPage.setConversation(null);
      this.__showConversation();
      conversationPage.postMessage(osparc.support.SupportCenter.REQUEST_CALL_MESSAGE)
        .then(data => {
          const conversationId = data["conversationId"];
          osparc.store.ConversationsSupport.getInstance().getConversation(conversationId)
            .then(conversation => {
              // update conversation name and patch extra_context
              conversation.renameConversation("Book a call");
              conversation.patchExtraContext({
                ...conversation.getExtraContext(),
                "appointment": "requested"
              });
              // This should be an automatic response in the chat
              const msg = this.tr("Your request has been sent.<br>Our support team will get back to you.");
              osparc.FlashMessenger.logAs(msg, "INFO");
            });
        })
        .catch(err => {
          console.error("Error sending request call message", err);
        });
    },
  }
});
