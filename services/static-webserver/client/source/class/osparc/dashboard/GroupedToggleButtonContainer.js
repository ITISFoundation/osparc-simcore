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

    const showAllButton = this.__showAllButton = new qx.ui.form.Button().set({
      margin: 10,
      marginBottom: 5
    });
    const headerBar = this.getChildControl("header-bar");
    headerBar.addAt(showAllButton, 1);

    this.__contentContainer = this.__createContentContainer();

    this.bind("expanded", showAllButton, "label", {
      converter: expanded => expanded ? this.tr("Show less") : this.tr("Show all")
    });
    showAllButton.addListener("execute", () => this.setExpanded(!this.isExpanded()));
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
    },

    expanded: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeExpanded",
      apply: "__applyExpanded"
    }
  },

  members: {
    __showAllButton: null,
    __contentContainer: null,

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
      }
      return control || this.base(arguments, id);
    },

    __createContentContainer: function() {
      let contentContainer = null;
      const expanded = this.isExpanded();
      const showAllBtn = this.__showAllButton;
      if (expanded) {
        contentContainer = new osparc.dashboard.ToggleButtonContainer();
        showAllBtn.show();
      } else {
        const spacing = osparc.dashboard.GridButtonBase.SPACING;
        contentContainer = new osparc.component.widget.SlideBar(spacing);
        contentContainer.setButtonsWidth(30);

        // show showAllBtn only if slidebar is full
        const buttonBackward = contentContainer.getChildControl("button-backward");
        const buttonForward = contentContainer.getChildControl("button-forward");
        buttonBackward.bind("visibility", showAllBtn, "visibility", {
          converter: visibility => (visibility === "visible" || buttonForward.isVisible()) ? "visible" : "excluded"
        });
        buttonForward.bind("visibility", showAllBtn, "visibility", {
          converter: visibility => (visibility === "visible" || buttonBackward.isVisible()) ? "visible" : "excluded"
        });
      }
      contentContainer.set({
        padding: 5,
        allowGrowX: false,
        backgroundColor: "background-main-1"
      });
      this._addAt(contentContainer, 1, {
        flex: 1
      });
      return contentContainer;
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

    __applyExpanded: function() {
      const children = this.__contentContainer.getChildren();
      this._remove(this.__contentContainer);

      this.__contentContainer = this.__createContentContainer();
      for (let i=children.length-1; i>=0; i--) {
        this.add(children[i], 0);
      }
    },

    getContentContainer: function() {
      return this.__contentContainer;
    },

    // overridden
    add: function(child, idx) {
      if (child instanceof qx.ui.form.ToggleButton) {
        child.addListener("changeVisibility", () => this.__childVisibilityChanged(), this);
        const container = this.getContentContainer();
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
      return this.__contentContainer.getChildren();
    },

    removeCard: function(key) {
      const cards = this.getCards();
      for (let i=0; i<cards.length; i++) {
        const card = cards[i];
        if (card.getUuid && key === card.getUuid()) {
          this.getContentContainer().remove(card);
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
