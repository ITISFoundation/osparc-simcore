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
    this.base(arguments, "support-center", "Support Center");

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
          this._add(control, {
            flex: 1
          });
          break;
        case "conversations-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.getChildControl("stack-layout").add(control);
          break;
        case "conversations-intro-text":
          control = new qx.ui.basic.Label(this.tr("Welcome to the Support Center"));
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
          control.addListener("execute", () => {
            this.__newConversation();
          });
          this.getChildControl("conversations-layout").add(control);
          break;
        case "conversation-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.getChildControl("stack-layout").add(control);
          break;
        case "conversation-intro-text":
          control = new qx.ui.basic.Label(this.tr("One conversation"));
          this.getChildControl("conversation-layout").add(control);
          break;
        case "conversation-content":
          control = new osparc.support.Conversation();
          this.getChildControl("conversation-layout").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __newConversation: function() {
      this.getChildControl("conversation-intro-text").setValue(this.tr("New conversation"));
      const conversation = this.getChildControl("conversation-content");
      this.getChildControl("stack-layout").setSelection([this.getChildControl("conversation-layout")]);
    },
  }
});
