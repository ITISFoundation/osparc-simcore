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

    this._createChildControlImpl("see-all-group");
  },

  properties: {
    groupId: {
      check: "String",
      init: null,
      nullable: false
    },

    headerLabel: {
      check: "String",
      apply: "__updateHeaderLabel"
    },

    headerIcon: {
      check: "String",
      apply: "__updateHeaderIcon"
    },

    headerColor: {
      check: "String",
      apply: "__updateHeaderColor"
    }
  },

  events: {
    "seeAllPressed": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "header-bar":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          this._addAt(control, 0);
          break;
        case "header": {
          control = new qx.ui.basic.Atom().set({
            font: "title-14",
            gap: 10,
            padding: 10,
            paddingBottom: 5,
            allowGrowX: false,
            backgroundColor: "background-main-1"
          });
          control.getContentElement().setStyles({
            "border-top-left-radius": "4px",
            "border-top-right-radius": "4px"
          });
          const headerBar = this.getChildControl("header-bar");
          headerBar.addAt(control, 0);
          break;
        }
        case "see-all-group": {
          control = new qx.ui.form.Button(this.tr("See all")).set({
            margin: 10,
            marginBottom: 5
          });
          control.addListener("execute", () => this.fireDataEvent("seeAllPressed", this.getGroupId()));
          const headerBar = this.getChildControl("header-bar");
          headerBar.addAt(control, 1);
          break;
        }
        case "content-container":
          control = new osparc.component.widget.SlideBar().set({
            padding: 5,
            allowGrowX: false,
            backgroundColor: "background-main-1"
          });
          control.setButtonsWidth(30);
          this._addAt(control, 1, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __updateHeaderLabel: function(label) {
      const atom = this.getChildControl("header");
      atom.setLabel(label);
    },

    __updateHeaderIcon: function(icon) {
      const atom = this.getChildControl("header");
      atom.setIcon(icon);
    },

    __updateHeaderColor: function(color) {
      const atom = this.getChildControl("header");
      atom.getChildControl("icon").setTextColor(color);
    },

    // overridden
    add: function(child, idx) {
      if (child instanceof qx.ui.form.ToggleButton) {
        child.addListener("changeVisibility", () => this.__childVisibilityChanged(), this);
        const container = this.getChildControl("content-container");
        if (idx === undefined) {
          container.add(child);
        } else {
          container.addAt(child, idx);
        }
        this.__childVisibilityChanged();
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
      const children = this.getCards();
      const anyVis = children.some(child => child.isVisible());
      this.set({
        visibility: anyVis ? "visible" : "excluded"
      });
    }
  }
});
