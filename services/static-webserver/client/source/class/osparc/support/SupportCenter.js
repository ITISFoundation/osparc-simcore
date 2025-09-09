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
    this.getChildControl("ask-a-question-button");
    this.getChildControl("book-a-call-button");
  },

  statics: {
    WINDOW_WIDTH: 430,
    REQUEST_CALL_MESSAGE: "Dear Support,\nI would like to make an appointment for a support call.",

    getMaxHeight: function() {
      // height: max 80% of screen, or 600px
      const clientHeight = document.documentElement.clientHeight;
      return Math.min(600, parseInt(clientHeight * 0.8));
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
          const isSupportUser = osparc.store.Groups.getInstance().amIASupportUser();
          control.set({
            value: isSupportUser ?
              this.tr("Thanks for being here! Let's help every user feel supported.") :
              this.tr("Need help or want to share feedback? You're in the right place."),
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
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignX: "center",
          }));
          this.getChildControl("conversations-layout").add(control);
          break;
        case "ask-a-question-button":
          control = new osparc.ui.form.FetchButton(this.tr("Ask a Question")).set({
            appearance: "strong-button",
            allowGrowX: false,
            center: true,
          });
          control.addListener("execute", () => this.openConversation(null), this);
          this.getChildControl("buttons-layout").add(control);
          break;
        case "book-a-call-button":
          control = new osparc.ui.form.FetchButton(this.tr("Book a Call")).set({
            appearance: "strong-button",
            allowGrowX: false,
            center: true,
          });
          control.addListener("execute", () => this.createConversationBookCall(null), this);
          this.getChildControl("buttons-layout").add(control);
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
