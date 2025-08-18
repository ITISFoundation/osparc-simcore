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
    this.base(arguments, "support-center", "Messages");

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
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.getChildControl("stack-layout").add(control);
          break;
        case "conversations-intro-text":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Welcome to the Support Center<br>Ask us anything, or share your feedback."),
            rich: true,
            font: "text-14",
          });
          this.getChildControl("conversations-layout").add(control);
          break;
        case "conversations-list": {
          control = new osparc.support.Conversations();
          const scroll = new qx.ui.container.Scroll();
          scroll.add(control);
          this.getChildControl("conversations-layout").add(scroll, {
            flex: 1,
          });
          break;
        }
        case "ask-a-question-button":
          control = new qx.ui.form.Button(this.tr("Ask a Question")).set({
            appearance: "strong-button",
            center: true,
          });
          control.addListener("execute", () => this.__openConversation(), this);
          this.getChildControl("conversations-layout").add(control);
          break;
        case "conversation-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.getChildControl("stack-layout").add(control);
          break;
        case "conversation-header":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this.getChildControl("conversation-layout").add(control);
          break;
        case "conversation-back-button":
          control = new qx.ui.form.Button().set({
            toolTipText: this.tr("Return to Messages"),
            icon: "@FontAwesome5Solid/arrow-left/16",
            backgroundColor: "transparent"
          });
          control.addListener("execute", () => this.__showConversations());
          this.getChildControl("conversation-header").add(control);
          break;
        case "conversation-content":
          control = new osparc.support.Conversation();
          const scroll = new qx.ui.container.Scroll();
          scroll.add(control);
          this.getChildControl("conversation-layout").add(scroll, {
            flex: 1,
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __showConversations: function() {
      this.getChildControl("stack-layout").setSelection([this.getChildControl("conversations-layout")]);
    },

    __showConversation: function() {
      this.getChildControl("stack-layout").setSelection([this.getChildControl("conversation-layout")]);
    },

    __openConversation: function(conversationId) {
      this.getChildControl("conversation-back-button").show();
      const conversationContent = this.getChildControl("conversation-content");
      if (conversationId) {
        conversationContent.setConversationId(conversationId);
      } else {
        conversationContent.setConversationId(null);
      }
      this.__showConversation();
    },
  }
});
