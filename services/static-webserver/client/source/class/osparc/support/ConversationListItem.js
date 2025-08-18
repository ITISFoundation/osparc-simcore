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

    /*
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
    */
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
    /*
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "thumbnail":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            scale: true,
            allowGrowX: true,
            allowGrowY: true,
            allowShrinkX: true,
            allowShrinkY: true,
            maxWidth: 32,
            maxHeight: 32
          });
          this._add(control, this.self().GRID_POS.THUMBNAIL);
          break;
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            alignY: "middle",
          });
          this._add(control, this.self().GRID_POS.TITLE);
          break;
        case "author":
          control = new qx.ui.basic.Label().set({
            font: "text-13"
          });
          this._add(control, this.self().GRID_POS.AUTHOR);
          break;
        case "author":
          control = new qx.ui.basic.Label().set({
            font: "text-13"
          });
          this._add(control, this.self().GRID_POS.LAST_MODIFIED);
          break;
        case "enter-button":
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/info/14"
          });
          this._add(control, this.self().GRID_POS.BUTTON);
          break;
      }

      return control || this.base(arguments, id);
    },
    */

    __applyConversationId: function(conversationId) {
      osparc.store.ConversationsSupport.getInstance().getLastMessage(conversationId)
        .then(lastMessages => {
          if (lastMessages && lastMessages.length) {
            this.set({
              title: lastMessages[0].title,
              author: lastMessages[0].author,
              lastModified: lastMessages[0].lastModified,
            });
          }
        });
    },
  }
});
