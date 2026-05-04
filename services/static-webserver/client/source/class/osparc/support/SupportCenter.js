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

    osparc.utils.Utils.setIdToWidget(this, "supportCenterWindow");

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
    if (osparc.store.Groups.getInstance().isSupportEnabled()) {
      this.getChildControl("conversations-page");
      this.getChildControl("conversation-page");
      this.getChildControl("home-button");
      this.getChildControl("conversations-button");
    }

    this.__selectHomeStackPage();
  },

  statics: {
    WINDOW_WIDTH: 450,
    WINDOW_HEIGHT: 700,
    REQUEST_CALL_MESSAGE: "Dear Support,\nI would like to make an appointment for a support call.",

    getMaxHeight: function() {
      // height: max 80% of screen, or WINDOW_HEIGHT px
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
          })).set({
            visibility: osparc.store.Groups.getInstance().isSupportEnabled() ? "visible" : "excluded",
          });
          this.add(control);
          break;
        case "home-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Help & Support"),
            icon: "@FontAwesome5Solid/question-circle/18",
            backgroundColor: "transparent",
            iconPosition: "top",
            allowGrowX: true,
            center: true,
          });
          control.addListener("execute", () => this.__selectHomeStackPage(), this);
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
        case "home-page-layout":
          control = new qx.ui.container.Scroll();
          this.getChildControl("main-stack").add(control);
          break;
        case "home-page":
          control = new osparc.support.HomePage();
          control.addListener("createConversation", e => this.createConversation(e.getData()), this);
          this.getChildControl("home-page-layout").add(control);
          break;
        case "conversations-layout":
          control = new qx.ui.container.Scroll();
          this.getChildControl("main-stack").add(control);
          break;
        case "conversations-stack":
          control = new qx.ui.container.Stack();
          this.getChildControl("conversations-layout").add(control);
          break;
        case "conversations-page":
          control = new osparc.support.ConversationsPage();
          control.addListener("openConversation", e => this.openConversation(e.getData()), this);
          control.addListener("createConversation", e => this.createConversation(e.getData()), this);
          this.getChildControl("conversations-stack").add(control);
          break;
        case "conversation-page":
          control = new osparc.support.ConversationPage();
          control.addListener("backToConversations", () => this.showConversations(), this);
          this.getChildControl("conversations-stack").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __selectHomeStackPage: function() {
      this.setCaption(this.tr("Help & Support"));
      this.getChildControl("main-stack").setSelection([this.getChildControl("home-page-layout")]);
      this.getChildControl("home-button").getChildControl("icon").set({
        textColor: "strong-main",
      });
      this.getChildControl("conversations-button").getChildControl("icon").set({
        textColor: "text",
      });
    },

    __selectConversationsStackPage: function() {
      this.setCaption(this.tr("Conversations"));
      this.getChildControl("main-stack").setSelection([this.getChildControl("conversations-layout")]);
      this.getChildControl("home-button").getChildControl("icon").set({
        textColor: "text",
      });
      this.getChildControl("conversations-button").getChildControl("icon").set({
        textColor: "strong-main",
      });
    },

    showConversations: function() {
      this.__selectConversationsStackPage();
      this.getChildControl("conversations-stack").setSelection([this.getChildControl("conversations-page")]);
    },

    __showConversation: function() {
      this.__selectConversationsStackPage();
      const conversationPage = this.getChildControl("conversation-page");
      this.getChildControl("conversations-stack").setSelection([conversationPage]);

      const conversation = conversationPage.getConversation();
      if (conversation) {
        if (osparc.store.Groups.getInstance().amIASupportUser() && conversation.isReadBySupport() === false) {
          conversation.markAsRead();
        } else if (!osparc.store.Groups.getInstance().amIASupportUser() && conversation.isReadByUser() === false) {
          conversation.markAsRead();
        }
      }
    },

    openConversation: function(conversationId) {
      const conversationPage = this.getChildControl("conversation-page");
      if (conversationId) {
        osparc.store.ConversationsSupport.getInstance().getConversation(conversationId)
          .then(conversation => {
            conversationPage.setConversation(conversation);
            this.__showConversation();
          });
      }
    },

    createConversation: function(type, prefillText) {
      const conversationPage = this.getChildControl("conversation-page");
      conversationPage.proposeConversation(type, prefillText);
      this.__showConversation();
    },
  }
});
