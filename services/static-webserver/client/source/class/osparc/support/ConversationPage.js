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


qx.Class.define("osparc.support.ConversationPage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this.__messages = [];

    this._setLayout(new qx.ui.layout.VBox(5));

    this.getChildControl("back-button");

    const conversation = this.getChildControl("conversation-content");
    this.bind("conversation", conversation, "conversation");
    conversation.bind("conversation", this, "conversation");
  },

  properties: {
    conversation: {
      check: "osparc.data.model.Conversation",
      init: null,
      nullable: true,
      event: "changeConversation",
      apply: "__applyConversation",
    },
  },

  events: {
    "showConversations": "qx.event.type.Event",
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "conversation-header-layout": {
          const headerLayout = new qx.ui.layout.HBox(5).set({
            alignY: "middle",
          })
          control = new qx.ui.container.Composite(headerLayout).set({
            padding: 5,
          });
          this._add(control);
          break;
        }
        case "back-button":
          control = new qx.ui.form.Button().set({
            toolTipText: this.tr("Return to Messages"),
            icon: "@FontAwesome5Solid/arrow-left/16",
            backgroundColor: "transparent"
          });
          control.addListener("execute", () => this.fireEvent("showConversations"));
          this.getChildControl("conversation-header-layout").addAt(control, 0);
          break;
        case "conversation-header-center-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.getChildControl("conversation-header-layout").addAt(control, 1, {
            flex: 1,
          });
          break;
        case "conversation-title":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            alignY: "middle",
            allowGrowX: true,
            });
          this.getChildControl("conversation-header-center-layout").addAt(control, 0);
          break;
        case "conversation-extra-content":
          control = new qx.ui.basic.Label().set({
            font: "text-12",
            textColor: "text-disabled",
            rich: true,
            allowGrowX: true,
            selectable: true,
          });
          this.getChildControl("conversation-header-center-layout").addAt(control, 1);
          break;
        case "conversation-options": {
          control = new qx.ui.form.MenuButton().set({
            maxWidth: 22,
            maxHeight: 22,
            alignX: "center",
            alignY: "middle",
            icon: "@FontAwesome5Solid/ellipsis-v/14",
          });
          const menu = new qx.ui.menu.Menu().set({
            position: "bottom-right",
          });
          control.setMenu(menu);
          const renameButton = new qx.ui.menu.Button().set({
            label: this.tr("Rename"),
            icon: "@FontAwesome5Solid/i-cursor/10"
          });
          renameButton.addListener("execute", () => this.__renameConversation());
          menu.add(renameButton);
          this.getChildControl("conversation-header-layout").addAt(control, 2);
          break;
        }
        case "conversation-content":
          control = new osparc.support.Conversation();
          const scroll = new qx.ui.container.Scroll();
          scroll.add(control);
          this._add(scroll, {
            flex: 1,
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyConversation: function(conversation) {
      const title = this.getChildControl("conversation-title");
      const options = this.getChildControl("conversation-options");
      if (conversation) {
        conversation.bind("nameAlias", title, "value");
        const amISupporter = osparc.store.Products.getInstance().amIASupportUser();
        const extraContextLabel = this.getChildControl("conversation-extra-content");
        extraContextLabel.setVisibility(amISupporter ? "visible" : "excluded");
        const extraContext = conversation.getExtraContext();
        if (amISupporter && extraContext && Object.keys(extraContext).length) {
          let extraContextText = `Support ID: ${conversation}`;
          const contextProjectId = conversation.getContextProjectId();
          if (contextProjectId) {
            extraContextText += `<br>Project ID: ${contextProjectId}`;
          }
          extraContextLabel.setValue(extraContextText);
        }
        options.show();
      } else {
        title.setValue("");
        options.exclude();
      }
    },

    __renameConversation: function() {
      let oldName = this.getConversation().getName();
      if (oldName === "null") {
        oldName = "";
      }
      const renamer = new osparc.widget.Renamer(oldName);
      renamer.addListener("labelChanged", e => {
        renamer.close();
        const newLabel = e.getData()["newLabel"];
        this.getConversation().renameConversation(newLabel);
      }, this);
      renamer.center();
      renamer.open();
    },
  }
});
