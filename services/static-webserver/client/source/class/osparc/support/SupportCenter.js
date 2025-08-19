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
    this.base(arguments, "support-center", "Support");

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

    this.getChildControl("conversations-intro-text");
    this.getChildControl("conversations-list");
    // if (!osparc.store.Products.getInstance().amIASupportUser()) {
      this.getChildControl("ask-a-question-button")
    // }
  },

  statics: {
    WINDOW_WIDTH: 400,

    getMaxHeight: function() {
      // height: max 80% of screen, min 600
      const clientHeight = document.documentElement.clientHeight;
      return Math.max(600, parseInt(clientHeight * 0.8));
    },

    openWindow: function() {
      const supportCenterWindow = new osparc.support.SupportCenter();

      const positionWindow = () => {
        supportCenterWindow.set({
          height: osparc.support.SupportCenter.getMaxHeight(),
        });
        // bottom right
        const clientWidth = document.documentElement.clientWidth;
        const clientHeight = document.documentElement.clientHeight;
        const posX = clientWidth - osparc.support.SupportCenter.WINDOW_WIDTH;
        const posY = clientHeight - supportCenterWindow.getHeight();
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
        case "stack-layout":
          control = new qx.ui.container.Stack();
          this.add(control, {
            flex: 1
          });
          break;
        case "conversations-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(15));
          this.getChildControl("stack-layout").add(control);
          break;
        case "conversations-intro-text": {
          control = new qx.ui.basic.Label().set({
            rich: true,
            font: "text-14",
          });
          const isSupportUser = osparc.store.Products.getInstance().amIASupportUser();
          control.set({
            value: isSupportUser ? this.tr("Here all the support questions") : this.tr("Ask us anything, or share your feedback."),
          });
          this.getChildControl("conversations-layout").add(control);
          break;
        }
        case "conversations-list": {
          control = new osparc.support.Conversations();
          control.addListener("openConversation", e => {
            const conversationId = e.getData();
            this.openConversation(conversationId);
          }, this);
          const scroll = new qx.ui.container.Scroll();
          scroll.add(control);
          this.getChildControl("conversations-layout").add(scroll, {
            flex: 1,
          });
          break;
        }
        case "ask-a-question-button":
          control = new osparc.ui.form.FetchButton(this.tr("Ask a Question")).set({
            appearance: "strong-button",
            allowGrowX: false,
            center: true,
            alignX: "center",
          });
          control.addListener("execute", () => this.openConversation(null), this);
          this.getChildControl("conversations-layout").add(control);
          break;
        case "conversation-page":
          control = new osparc.support.ConversationPage();
          control.addListener("showConversations", () => this.__showConversations(), this);
          this.getChildControl("stack-layout").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __showConversations: function() {
      this.getChildControl("stack-layout").setSelection([this.getChildControl("conversations-layout")]);
    },

    __showConversation: function() {
      this.getChildControl("stack-layout").setSelection([this.getChildControl("conversation-page")]);
    },

    openConversation: function(conversationId) {
      const conversationContent = this.getChildControl("conversation-page");
      conversationContent.setConversationId(conversationId);
      this.__showConversation();
    },

    __createConversation: function() {
      this.getChildControl("ask-a-question-button").setFetching(true);
      osparc.store.ConversationsSupport.getInstance().addConversation()
        .then(data => {
          this.openConversation(data["conversationId"]);
        })
        .finally(() => {
          this.getChildControl("ask-a-question-button").setFetching(false);
        });
    },
  }
});
