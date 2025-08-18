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

qx.Class.define("osparc.support.ConversationListItem", {
  extend: osparc.ui.list.ListItem,

  construct: function() {
    this.base(arguments);

    const layout = this._getLayout();
    layout.setSpacingX(10);
    layout.setSpacingY(10);
    layout.setColumnFlex(this.self().GRID_POS.ICON, 0);
  },

  properties: {
    conversationId: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changeConversationId",
      apply: "__applyConversationId",
    },

    thumbnail: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeThumbnail",
    },

    title: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeTitle",
    },

    author: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeAuthor",
    },

    lastModified: {
      check: "Date",
      init: null,
      nullable: false,
      event: "changeLastModified",
    },
  },

  statics: {
    GRID_POS: {
      THUMBNAIL: {
        row: 0,
        column: 0,
        rowSpan: 2,
      },
      TITLE: {
        row: 0,
        column: 1,
        colSpan: 2,
      },
      AUTHOR: {
        row: 1,
        column: 1,
      },
      LAST_MODIFIED: {
        row: 1,
        column: 2,
      },
      BUTTON: {
        row: 0,
        column: 3,
        rowSpan: 2
      },
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "card-holder-name":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: this.self().GRID_POS.NAME
          });
          break;
        case "card-type":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: this.self().GRID_POS.TYPE
          });
          break;
        case "card-number-masked":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: this.self().GRID_POS.MASKED_NUMBER
          });
          break;
        case "expiration-date":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: this.self().GRID_POS.EXPIRATION_DATE
          });
          break;
        case "details-button":
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/info/14"
          });
          control.addListener("execute", () => this.fireDataEvent("openPaymentMethodDetails", this.getKey()));
          this._add(control, {
            row: 0,
            column: this.self().GRID_POS.INFO_BUTTON
          });
          break;
        case "delete-button":
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/trash/14"
          });
          control.addListener("execute", () => this.__deletePressed());
          this._add(control, {
            row: 0,
            column: this.self().GRID_POS.DELETE_BUTTON
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __applyConversationId: function(conversationId) {
      osparc.store.ConversationsSupport.getInstance().getConversation(conversationId)
        .then(conversation => {
          this.set({
            title: conversation.title,
            author: conversation.author,
            lastModified: conversation.lastModified,
          });
        });
    },
  }
});
