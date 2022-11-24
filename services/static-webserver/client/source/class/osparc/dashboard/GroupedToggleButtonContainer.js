/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.GroupedToggleButtonContainer", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    const container = this.__container = new osparc.component.widget.SlideBar();
    container.setButtonsWidth(30);
    this._addAt(container, 1);
  },

  properties: {
    groupId: {
      check: "String",
      init: null,
      nullable: false
    },

    groupHeader: {
      // check: qx.ui.core.Widget,
      init: null,
      nullable: true,
      apply: "__applyGroupHeader"
    }
  },

  members: {
    __container: null,

    __applyGroupHeader: function(header) {
      this._removeAt(0);
      this._addAt(header, 0);
    },

    // overridden
    add: function(child, idx) {
      if (child instanceof qx.ui.form.ToggleButton) {
        child.addListener("changeVisibility", () => this.__childVisibilityChanged(), this);
        if (idx === undefined) {
          this.__container.add(child);
        } else {
          this.__container.addAt(child, idx);
        }
      } else {
        console.error("ToggleButtonContainer only allows ToggleButton as its children.");
      }
    },

    getCards: function() {
      return this.__container.getChildren();
    },

    removeCard: function(key) {
      const cards = this.getChildren();
      for (let i=0; i<cards.length; i++) {
        const card = cards[i];
        if (card.getUuid && key === card.getUuid()) {
          this.remove(card);
          return;
        }
      }
    },

    __childVisibilityChanged: function() {
      const children = this.__container.getChildren();
      this.__container.set({
        visibility: children.any(child => child.isVisible()) ? "visible" : "excluded"
      });
    }
  }
});
