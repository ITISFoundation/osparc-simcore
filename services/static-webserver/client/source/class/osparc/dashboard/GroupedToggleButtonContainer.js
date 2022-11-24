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
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "content-container":
          control = new osparc.component.widget.SlideBar();
          control.setButtonsWidth(30);
          this._addAt(control, 1, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyGroupHeader: function(newHeader, oldHeader) {
      if (oldHeader) {
        this._remove(oldHeader);
      }
      this._addAt(newHeader, 0);
    },

    // overridden
    add: function(child, idx) {
      if (child instanceof qx.ui.form.ToggleButton) {
        child.addListener("changeVisibility", () => this.__childVisibilityChanged(), this);
        if (idx === undefined) {
          this.getChildControl("content-container").add(child);
        } else {
          this.getChildControl("content-container").addAt(child, idx);
        }
      } else {
        console.error("ToggleButtonContainer only allows ToggleButton as its children.");
      }
    },

    getCards: function() {
      return this.getChildControl("content-container").getChildren();
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
      const children = this.getChildControl("content-container").getChildren();
      this.getChildControl("content-container").set({
        visibility: children.any(child => child.isVisible()) ? "visible" : "excluded"
      });
    }
  }
});
