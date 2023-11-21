/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)

************************************************************************ */

/**
 * Widget used by StudyBrowser and Explore Browser for displaying Studies, Templates and Services
 */

qx.Class.define("osparc.dashboard.GridButtonBase", {
  extend: osparc.dashboard.CardBase,
  type: "abstract",

  construct: function() {
    this.base(arguments);

    this.set({
      width: this.self().ITEM_WIDTH,
      height: this.self().ITEM_HEIGHT,
      padding: 0,
      allowGrowX: false
    });

    this._setLayout(new qx.ui.layout.Canvas());

    const grid = new qx.ui.layout.Grid();
    grid.setSpacing(this.self().SPACING_IN);
    grid.setRowFlex(2, 1);
    grid.setColumnFlex(0, 1);
    grid.setRowMaxHeight(0, this.self().TITLE_MAX_HEIGHT);

    const mainLayout = this._mainLayout = new qx.ui.container.Composite().set({
      maxWidth: this.self().ITEM_WIDTH,
      maxHeight: this.self().ITEM_HEIGHT
    });
    mainLayout.setLayout(grid);

    this._add(mainLayout, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });
  },

  statics: {
    ITEM_WIDTH: 190,
    ITEM_HEIGHT: 220,
    PADDING: 10,
    SPACING_IN: 5,
    SPACING: 15,
    // TITLE_MAX_HEIGHT: 34, // two lines in Roboto
    TITLE_MAX_HEIGHT: 44, // two lines in Manrope
    POS: {
      TITLE: {
        row: 0,
        column: 0,
        rowSpan: 1,
        colSpan: 4
      },
      SUBTITLE: {
        row: 1,
        column: 0,
        rowSpan: 1,
        colSpan: 3
      },
      THUMBNAIL: {
        row: 2,
        column: 0,
        rowSpan: 1,
        colSpan: 4
      },
      STATUS: {
        row: 2,
        column: 0
      },
      TAGS: {
        row: 3,
        column: 0
      },
      TSR: {
        row: 4,
        column: 0
      },
      VIEWER_MODE: {
        row: 3,
        column: 1,
        rowSpan: 2,
        colSpan: 1
      },
      UPDATES: {
        row: 3,
        column: 2,
        rowSpan: 2,
        colSpan: 1
      },
      FOOTER: {
        row: 4,
        column: 0,
        rowSpan: 1,
        colSpan: 4
      }
    }
  },

  events: {
    /** (Fired by {@link qx.ui.form.List}) */
    "action": "qx.event.type.Event"
  },

  members: {
    _mainLayout: null,

    // overridden
    _createChildControlImpl: function(id) {
      let layout;
      let control;
      switch (id) {
        case "header":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
            anonymous: true,
            allowGrowX: true,
            allowShrinkX: false,
            alignY: "middle",
            padding: this.self().PADDING
          });
          control.set({
            backgroundColor: "background-card-overlay"
          });
          this._mainLayout.add(control, this.self().POS.TITLE);
          break;
        case "body":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
            decorator: "main",
            allowGrowY: true,
            allowGrowX: true,
            allowShrinkX: true,
            padding: this.self().PADDING,
          });
          control.getContentElement().setStyles({
            "border-width": 0
          });
          this._mainLayout.add(control, this.self().POS.THUMBNAIL);
          break;
        case "footer":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
            visibility: "excluded",
            anonymous: true,
            allowGrowX: true,
            allowShrinkX: false,
            padding: this.self().PADDING,
            backgroundColor: "background-card-overlay"
          });
          control.setAlignY("bottom");
          this._applyFooter();
          this._mainLayout.add(control, this.self().POS.FOOTER);
          break;
        case "title-row":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(6)).set({
            anonymous: true
          });
          layout = this.getChildControl("header");
          layout.addAt(control, 1, {
            flex: 1
          });
          break;
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "text-16",
            maxWidth: this.self().ITEM_WIDTH,
            maxHeight: this.self().TITLE_MAX_HEIGHT,
            rich: true,
            wrap: true
          });
          layout = this.getChildControl("title-row");
          layout.addAt(control, 0, {
            flex: 1
          });
          break;
        case "subtitle":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(6)).set({
            anonymous: true
          });
          layout = this.getChildControl("header");
          layout.addAt(control, 1, {
            flex: 1
          });
          break;
        case "subtitle-icon": {
          control = new qx.ui.basic.Image().set({
            alignY: "middle"
          });
          const subtitleLayout = this.getChildControl("subtitle");
          subtitleLayout.addAt(control, 0);
          break;
        }
        case "subtitle-text": {
          control = new qx.ui.basic.Label().set({
            alignY: "middle",
            rich: true,
            anonymous: true,
            font: "text-12",
            allowGrowY: false
          });
          const subtitleLayout = this.getChildControl("subtitle");
          subtitleLayout.addAt(control, 1, {
            flex: 1
          });
          break;
        }
        case "icon": {
          layout = this.getChildControl("body");
          const maxWidth = this.self().ITEM_WIDTH;
          control = new osparc.ui.basic.Thumbnail(null, maxWidth, 124);
          control.getChildControl("image").set({
            anonymous: true,
            alignY: "middle",
            alignX: "center",
            allowGrowX: true,
            allowGrowY: true
          });
          layout.getContentElement().setStyles({
            "border-width": "0px"
          });
          layout.add(control, {flex: 1});
          break;
        }
        case "project-status":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(6)).set({
            anonymous: true
          });
          layout = this.getChildControl("footer");
          layout.add(control);
          break;
        case "project-status-icon":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            textColor: "status_icon",
            height: 20,
            width: 20,
            padding: 3
          });
          layout = this.getChildControl("project-status");
          layout.addAt(control, 0);
          break;
        case "project-status-label":
          control = new qx.ui.basic.Label().set({
            alignY: "middle",
            rich: true,
            anonymous: true,
            font: "text-12",
            allowGrowY: false
          });
          layout = this.getChildControl("project-status");
          layout.addAt(control, 1, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    // overridden
    _applyIcon: function(value, old) {
      if (value.includes("@FontAwesome5Solid/")) {
        value += "50";
        const image = this.getChildControl("icon").getChildControl("image");
        image.set({
          source: value
        });

        [
          "appear",
          "loaded"
        ].forEach(eventName => {
          image.addListener(eventName, () => this.__fitIconHeight(), this);
        });
      } else {
        this.getContentElement().setStyles({
          "background-image": `url(${value})`,
          "background-repeat": "no-repeat",
          "background-size": "cover", // auto width, 85% height
          "background-position": "center center",
          "background-origin": "border-box"
        });
      }
    },

    // overridden
    _applyTitle: function(value, old) {
      const label = this.getChildControl("title");
      label.setValue(value);
      label.addListener("appear", () => {
        qx.event.Timer.once(() => {
          const labelDom = label.getContentElement().getDomElement();
          if (label.getMaxWidth() === parseInt(labelDom.style.width)) {
            label.setToolTipText(value);
          }
        }, this, 50);
      });
    },

    // overridden
    _applyDescription: function() {
      return;
    },

    _applyFooter: function() {
      debugger;
      const footer = this.getChildControl("footer");
      // const checkThis = ["tsr-rating", "project-status"];
      const isVisible = this._mainLayout._getChildren().includes("tsr-rating" || "project-status")
      footer.setVisibility(isVisible ? "visible" : "excluded");
    },

    __fitIconHeight: function() {
      const iconLayout = this.getChildControl("icon");
      let maxHeight = this.getHeight() - this.getPaddingTop() - this.getPaddingBottom() - 5;
      const checkThis = [
        "title",
        "subtitle",
        "tsr-rating",
        "tags"
      ];
      // eslint-disable-next-line no-underscore-dangle
      this._mainLayout._getChildren().forEach(child => {
        if (checkThis.includes(child.getSubcontrolId()) && child.getBounds()) {
          maxHeight -= (child.getBounds().height + this.self().SPACING_IN);
          if (child.getSubcontrolId() === "tags") {
            maxHeight -= 8;
          }
        }
      });
      // maxHeight -= 4; // for Roboto
      maxHeight -= 18; // for Manrope
      iconLayout.getChildControl("image").setMaxHeight(maxHeight);
      iconLayout.setMaxHeight(maxHeight);
      iconLayout.recheckSize();
    },

    /**
     * Event handler for the pointer over event.
     */
    _onPointerOver: function() {
      this.addState("hovered");
    },

    /**
     * Event handler for the pointer out event.
     */
    _onPointerOut : function() {
      this.removeState("hovered");
    },

    /**
     * Event handler for filtering events.
     */
    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    }
  },

  destruct : function() {
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
