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
     * Julian Querido (jsaq007)

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

    this.getChildControl("main-layout");
  },

  statics: {
    ITEM_WIDTH: 190,
    ITEM_HEIGHT: 220,
    PADDING: 10,
    SPACING_IN: 5,
    SPACING: 15,
    // TITLE_MAX_HEIGHT: 34, // two lines in Roboto
    TITLE_MAX_HEIGHT: 40, // two lines in Manrope
    ICON_SIZE: 50,
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
      FOOTER: {
        row: 4,
        column: 0,
        rowSpan: 1,
        colSpan: 4
      }
    },
    FPOS: {
      MODIFIED: {
        row: 0,
        column: 0,
      },
      UI_MODE: {
        row: 0,
        column: 1,
      },
      UPDATES: {
        row: 0,
        column: 2,
      },
      TSR: {
        row: 1,
        column: 0,
      },
      HITS: {
        row: 1,
        column: 1,
      },
      PERMISSION: {
        row: 1,
        column: 2,
      }
    }
  },

  events: {
    /** (Fired by {@link qx.ui.form.List}) */
    "action": "qx.event.type.Event"
  },

  members: {

    // overridden
    _createChildControlImpl: function(id) {
      let layout;
      let control;
      switch (id) {
        case "main-layout": {
          const grid = new qx.ui.layout.Grid();
          grid.setSpacing(this.self().SPACING_IN);
          grid.setRowFlex(2, 1);
          grid.setColumnFlex(0, 1);
          grid.setRowMaxHeight(0, this.self().TITLE_MAX_HEIGHT);

          control = new qx.ui.container.Composite().set({
            maxWidth: this.self().ITEM_WIDTH,
            maxHeight: this.self().ITEM_HEIGHT
          });
          control.setLayout(grid);
          const header = this.getChildControl("header");
          const body = this.getChildControl("body");
          const footer = this.getChildControl("footer");
          control.add(header, this.self().POS.TITLE);
          control.add(body, this.self().POS.THUMBNAIL);
          control.add(footer, this.self().POS.FOOTER);
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
        }
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
          break;
        case "footer": {
          const fgrid = new qx.ui.layout.Grid();
          fgrid.setSpacing(2);
          fgrid.setColumnFlex(0, 1);
          control = new qx.ui.container.Composite().set({
            backgroundColor: "background-card-overlay",
            padding: this.self().PADDING - 2,
            maxWidth: this.self().ITEM_WIDTH,
            maxHeight: this.self().ITEM_HEIGHT
          });
          control.setLayout(fgrid);
          break;
        }
        case "title-row":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(6)).set({
            anonymous: true,
            maxWidth: this.self().ITEM_WIDTH - 2*this.self().PADDING
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
            maxWidth: this.self().ITEM_WIDTH - 2*this.self().PADDING,
            maxHeight: this.self().TITLE_MAX_HEIGHT
          });
          layout = this.getChildControl("title-row");
          layout.addAt(control, 0, {
            flex: 1
          });
          break;
        case "subtitle":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(6)).set({
            anonymous: true,
            height: 20
          });
          layout = this.getChildControl("title-row");
          layout.addAt(control, 1, {
            flex: 1
          });
          break;
        case "subtitle-icon": {
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            allowGrowX: false,
            allowShrinkX: false
          });
          const subtitleLayout = this.getChildControl("subtitle");
          subtitleLayout.addAt(control, 0);
          break;
        }
        case "subtitle-text": {
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-dark",
            alignY: "middle",
            allowGrowX: true,
            allowShrinkX: true,
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
        case "modified-text":
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-dark",
            alignY: "middle",
            rich: true,
            anonymous: true,
            font: "text-12",
            allowGrowY: false
          });
          layout = this.getChildControl("footer");
          layout.add(control, this.self().FPOS.MODIFIED);
          break;
        case "project-status":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            textColor: "status_icon",
            height: 13,
            width: 13,
            margin: [0, 1]
          });
          layout = this.getChildControl("subtitle");
          layout.set({
            visibility: "visible"
          });
          layout.addAt(control, 2);
          break;
      }
      return control || this.base(arguments, id);
    },

    // overridden
    _applyIcon: function(value, old) {
      if (value.includes("@FontAwesome5Solid/")) {
        value += this.self().ICON_SIZE;
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
      label.setToolTipText(value);
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
      const layout = this.getChildControl("main-layout");
      // eslint-disable-next-line no-underscore-dangle
      layout._getChildren().forEach(child => {
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

    replaceIcon: function(newIcon) {
      const plusIcon = this.getChildControl("icon");
      plusIcon.exclude();

      const bodyLayout = this.getChildControl("body");
      bodyLayout.add(newIcon, {flex: 1});
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
