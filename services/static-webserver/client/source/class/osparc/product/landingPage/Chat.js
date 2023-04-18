/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.landingPage.Chat", {
  extend: qx.ui.core.Widget,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      zIndex: 100000
    });

    this.getChildControl("chat-button");
  },

  statics: {
    PHRASES: [
      "All our dreams can come true, if we have the courage to pursue them.",
      "The secret of getting ahead is getting started.",
      "I've missed more than 9,000 shots in my career. I've lost almost 300 games. 26 times I've been trusted to take the game winning shot and missed. I've failed over and over and over again in my life, and that is why I succeed.",
      "Don't limit yourself. Many people limit themselves to what they think they can do. You can go as far as your mind lets you. What you believe, remember, you can achieve.",
      "The best time to plant a tree was 20 years ago. The second best time is now.",
      "Only the paranoid survive.",
      "It's hard to beat a person who never gives up.",
      "I wake up every morning and think to myself, 'How far can I push this company in the next 24 hours'.",
      "If people are doubting how far you can go, go so far that you can't hear them anymore.",
      "We need to accept that we won't always make the right decisions, that we'll screw up royally sometimes―understanding that failure is not the opposite of success, it's part of success.",
      "Write it. Shoot it. Publish it. Crochet it. Sauté it. Whatever. MAKE.",
      "The same boiling water that softens the potato hardens the egg. It's what you're made of. Not the circumstances.",
      "If we have the attitude that it's going to be a great day it usually is.",
      "You can either experience the pain of discipline or the pain of regret. The choice is yours.",
      "Impossible is just an opinion.",
      "Your passion is waiting for your courage to catch up.",
      "Magic is believing in yourself. If you can make that happen, you can make anything happen.",
      "If something is important enough, even if the odds are stacked against you, you should still do it.",
      "Hold the vision, trust the process.",
      "Don't be afraid to give up the good to go for the great.",
      "People who wonder if the glass is half empty or full miss the point. The glass is refillable."
    ]
  },

  members: {
    __chatBuble: null,

    _createChildControlImpl: function(id) {
      const iconSize = 64;
      let control;
      switch (id) {
        case "chat-button": {
          const imgSize = 28;
          const imgClosed = "@FontAwesome5Solid/envelope/"+imgSize;
          const imgOpened = "@FontAwesome5Solid/chevron-down/"+imgSize;
          control = new qx.ui.basic.Image(imgClosed).set({
            backgroundColor: "strong-main",
            textColor: "text",
            width: iconSize,
            height: iconSize,
            scale: true,
            paddingTop: parseInt(iconSize/2 - imgSize/2),
            cursor: "pointer"
          });
          control.addListener("tap", () => {
            if (control.getSource() === imgClosed) {
              control.setSource(imgOpened);
              this.__openChat();
            } else {
              control.setSource(imgClosed);
              this.__closeChat();
            }
          }, this);
          control.getContentElement().setStyles({
            "border-radius": "48px"
          });
          this._add(control, {
            bottom: 0,
            right: 0
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    start: function() {
      const root = qx.core.Init.getApplication().getRoot();
      root.add(this, {
        bottom: 20,
        right: 20
      });
    },

    stop: function() {
      this.__closeChat();
      const root = qx.core.Init.getApplication().getRoot();
      root.remove(this);
    },

    __createChat: function() {
      const chatLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(0, null, "separator-vertical")).set({
        padding: 5,
        paddingBottom: 0,
        backgroundColor: "contrasted-text-light"
      });
      chatLayout.getContentElement().setStyles({
        "border-radius": "8px"
      });

      const chatMessages = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        backgroundColor: "contrasted-text-light",
        minHeight: 200,
        maxHeight: 500
      });
      const scrollMessages = new qx.ui.container.Scroll();
      scrollMessages.add(chatMessages);
      chatLayout.add(scrollMessages, {
        flex: 1
      });

      const addMessage = (msg, who) => {
        const message = new qx.ui.basic.Label().set({
          font: "text-14",
          rich: true,
          backgroundColor: "contrasted-text-light",
          textColor: "contrasted-text-dark"
        });
        if (who === "user") {
          message.set({
            value: "<b>You</b>: " + msg,
            textAlign: "left"
          });
        } else {
          message.set({
            value: "<b>App team</b>: " + msg,
            alignX: "right",
            textAlign: "right"
          });
        }
        chatMessages.add(message);
      };

      const typeMessage = new qx.ui.form.TextField().set({
        placeholder: this.tr(" Write your message..."),
        backgroundColor: "contrasted-text-light",
        textColor: "contrasted-text-dark",
        font: "text-14",
        height: 30
      });
      const phrases = this.self().PHRASES;
      typeMessage.addListener("keypress", e => {
        if (e.getKeyIdentifier() === "Enter") {
          addMessage(typeMessage.getValue(), "user");
          typeMessage.setValue("");
          setTimeout(() => {
            const idx = Math.floor(Math.random() * phrases.length);
            addMessage(phrases[idx], "app-team");
          }, 1000);
        }
      }, this);
      chatLayout.add(typeMessage);

      return chatLayout;
    },

    __createChatLayout: function() {
      const chatLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        backgroundColor: "strong-main",
        padding: 15,
        width: 400
      });
      chatLayout.getContentElement().setStyles({
        "border-radius": "8px"
      });

      const introLabel = new qx.ui.basic.Label().set({
        value: this.tr("Hi there, this is the App Team. How can we help you?"),
        font: "text-18",
        maxWidth: 240,
        textAlign: "center",
        alignX: "center",
        rich: true,
        wrap: true
      });
      chatLayout.add(introLabel);

      const appTeamLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignX: "center",
        alignY: "middle"
      }));

      const size = 48;
      [{
        user: "https://github.com/drniiken",
        avatar: "https://avatars.githubusercontent.com/u/32800795"
      }, {
        user: "https://github.com/eofli",
        avatar: "https://avatars.githubusercontent.com/u/40888440"
      }].forEach(user => {
        const link = user.avatar + "?s=" + size;
        const image = new qx.ui.basic.Image().set({
          source: link,
          scale: true,
          maxWidth: size,
          maxHeight: size,
          cursor: "pointer"
        });
        image.addListener("tap", () => window.open(user.user, "_blank"));
        image.getContentElement().setStyles({
          "border-radius": "16px"
        });
        appTeamLayout.add(image);
      });
      chatLayout.add(appTeamLayout);

      const chat = this.__createChat();
      chatLayout.add(chat);

      return chatLayout;
    },

    __openChat: function() {
      if (this.__chatBuble === null) {
        this.__chatBuble = this.__createChatLayout();

        const root = qx.core.Init.getApplication().getRoot();
        root.add(this.__chatBuble, {
          bottom: 64+20+20,
          right: 20
        });
      }
      this.__chatBuble.show();
    },

    __closeChat: function() {
      if (this.__chatBuble) {
        this.__chatBuble.exclude();
      }
    }
  }
});
