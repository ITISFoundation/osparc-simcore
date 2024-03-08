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

    const fgrid = new qx.ui.layout.Grid();
    fgrid.setSpacing(2);
    fgrid.setRowFlex(2, 1);
    fgrid.setColumnFlex(0, 1);

    const footerLayout = this._footerLayout = new qx.ui.container.Composite().set({
      backgroundColor: "background-card-overlay",
      padding: this.self().PADDING - 2,
      maxWidth: this.self().ITEM_WIDTH,
      maxHeight: this.self().ITEM_HEIGHT
    });
    footerLayout.setLayout(fgrid);
    this._mainLayout.add(footerLayout, this.self().POS.FOOTER);
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
      THUMBNAIL: {
        row: 2,
        column: 0,
        rowSpan: 1,
        colSpan: 4
      },
      TAGS: {
        row: 3,
        column: 0
      },
      VIEWER_MODE: {
        row: 3,
        column: 1,
        rowSpan: 2,
        colSpan: 1
      },
      FOOTER: {
        row: 4,
        column: 0,
        rowSpan: 1,
        colSpan: 4
      }
    },
    FPOS: {
      STATUS: {
        row: 0,
        column: 0,
        rowSpan: 1,
        colSpan: 4
      },
      MODIFIED: {
        row: 1,
        column: 0,
        rowSpan: 1,
        colSpan: 3
      },
      UPDATES: {
        row: 1,
        column: 4,
        colSpan: 1
      },
      TSR: {
        row: 3,
        column: 0,
        colSpan: 2
      },
      HITS: {
        row: 3,
        column: 2,
        colSpan: 1
      }
    }
  },

  events: {
    /** (Fired by {@link qx.ui.form.List}) */
    "action": "qx.event.type.Event"
  },

  members: {
    _mainLayout: null,
    _footerLayout: null,

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
            padding: this.self().PADDING
          });
          control.getContentElement().setStyles({
            "border-width": 0
          });
          this._mainLayout.add(control, this.self().POS.THUMBNAIL);
          break;
        case "title-row":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(6)).set({
            anonymous: true
          });
          layout = this.getChildControl("header");
          layout.addAt(control, 1, {
            flex: 1
          });
          break;
        case "title":
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-light",
            font: "text-14",
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
          layout = this.getChildControl("title-row");
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
            textColor: "contrasted-text-dark",
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
        case "modified-text": {
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-dark",
            alignY: "middle",
            rich: true,
            anonymous: true,
            font: "text-12",
            allowGrowY: false
          });
          this._footerLayout.add(control, this.self().FPOS.MODIFIED);
          break;
        }
        case "project-status":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(6)).set({
            anonymous: true
          });
          this._footerLayout.add(control, this.self().FPOS.STATUS);
          break;
        case "project-status-icon":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            textColor: "status_icon",
            height: 12,
            width: 12,
            padding: 1
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

    __fitIconHeight: function() {
      const iconLayout = this.getChildControl("icon");
      let maxHeight = this.getHeight() - this.getPaddingTop() - this.getPaddingBottom() - 5;
      const checkThis = [
        "title",
        "body",
        "footer",
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
