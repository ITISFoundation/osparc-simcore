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

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      width: this.self().ITEM_WIDTH,
      height: this.self().ITEM_HEIGHT,
      padding: 0,
      allowGrowX: false
    });

    this.getChildControl("main-layout");
  },

  statics: {
    ITEM_WIDTH: 190,
    ITEM_HEIGHT: 220,
    PADDING: 6,
    SPACING: 15,
    THUMBNAIL_SIZE: 50,
    POS: {
      TITLE: {
        row: 0,
        column: 0,
      },
      BODY: {
        row: 1,
        column: 0,
      },
      FOOTER: {
        row: 2,
        column: 0,
      }
    },
    HPOS: {
      ICON: {
        column: 0,
        row: 0,
      },
      TITLE: {
        column: 1,
        row: 0,
      },
      SUBTITLE_ICON: {
        column: 0,
        row: 1,
      },
      SUBTITLE_TEXT: {
        column: 1,
        row: 1,
      },
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
    },
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
          grid.setRowFlex(this.self().POS.BODY.row, 1);
          grid.setColumnFlex(0, 1);

          control = new qx.ui.container.Composite().set({
            minWidth: this.self().ITEM_WIDTH,
            minHeight: this.self().ITEM_HEIGHT,
            maxWidth: this.self().ITEM_WIDTH,
            maxHeight: this.self().ITEM_HEIGHT,
          });
          control.setLayout(grid);
          const header = this.getChildControl("header");
          const body = this.getChildControl("body");
          const footer = this.getChildControl("footer");
          control.add(header, this.self().POS.TITLE);
          control.add(body, this.self().POS.BODY);
          control.add(footer, this.self().POS.FOOTER);
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
        }
        case "header": {
          const hGrid = new qx.ui.layout.Grid().set({
            spacing: 6,
          });
          hGrid.setRowFlex(this.self().HPOS.TITLE.row, 1);
          hGrid.setColumnFlex(this.self().HPOS.TITLE.column, 1);
          hGrid.setColumnAlign(0, "right", "middle");
          hGrid.setColumnAlign(1, "left", "middle");
          hGrid.setColumnAlign(2, "center", "middle");
          control = new qx.ui.container.Composite().set({
            backgroundColor: "background-card-overlay",
            paddingBottom: 6,
            paddingRight: 4,
            maxWidth: this.self().ITEM_WIDTH,
            minHeight: 32 + 6,
            maxHeight: this.self().ITEM_HEIGHT
          });
          control.setLayout(hGrid);
          break;
        }
        case "body":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(6)).set({
            padding: this.self().PADDING,
            alignY: "bottom",
          });
          break;
        case "footer": {
          const fGrid = new qx.ui.layout.Grid();
          fGrid.setSpacing(2);
          fGrid.setColumnFlex(this.self().FPOS.MODIFIED.row, 1);
          control = new qx.ui.container.Composite().set({
            backgroundColor: "background-card-overlay",
            padding: this.self().PADDING,
            maxWidth: this.self().ITEM_WIDTH,
            maxHeight: this.self().ITEM_HEIGHT
          });
          control.setLayout(fGrid);
          break;
        }
        case "icon": {
          control = osparc.dashboard.CardBase.createCardIcon();
          layout = this.getChildControl("header");
          layout.add(control, this.self().HPOS.ICON);
          break;
        }
        case "title":
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-light",
            font: "text-14",
          });
          layout = this.getChildControl("header");
          layout.add(control, this.self().HPOS.TITLE);
          break;
        case "subtitle-icon": {
          control = new qx.ui.basic.Image().set({
            allowGrowX: false,
            allowShrinkX: false,
          });
          layout = this.getChildControl("header");
          layout.add(control, this.self().HPOS.SUBTITLE_ICON);
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
          layout = this.getChildControl("header");
          layout.add(control, this.self().HPOS.SUBTITLE_TEXT);
          break;
        }
        case "thumbnail": {
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
        case "date-by":
          control = new osparc.ui.basic.DateAndBy();
          layout = this.getChildControl("footer");
          layout.add(control, this.self().FPOS.MODIFIED);
          break;
        case "project-status":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            textColor: "text",
            height: 13,
            width: 13,
            margin: [0, 1]
          });
          layout = this.getChildControl("header");
          layout.add(control, {
            column: 2,
            row: 1,
          });
          layout.addAt(control, 2);
          break;
      }
      return control || this.base(arguments, id);
    },

    // overridden
    _applyIcon: function(value, old) {
      if (value) {
        const image = this.getChildControl("icon").getChildControl("image");
        image.set({
          source: value,
        });
        osparc.utils.Utils.setAltToImage(image, "card-icon");
      }
    },

    // overridden
    _applyThumbnail: function(value, old) {
      if (qx.util.ResourceManager.getInstance().isFontUri(value)) {
        value += this.self().THUMBNAIL_SIZE;
        this.getChildControl("thumbnail").set({
          source: value,
        });
      } else {
        let source = osparc.product.Utils.getThumbnailUrl();
        osparc.utils.Utils.checkImageExists(value)
          .then(exists => {
            if (exists) {
              source = value;
            }
          })
          .finally(() => {
            this.getContentElement().setStyles({
              "background-image": `url(${source})`,
              "background-repeat": "no-repeat",
              "background-size": "cover", // auto width, 85% height
              "background-position": "center center",
              "background-origin": "border-box"
            });
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
