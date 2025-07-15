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
    PADDING: 8,
    SPACING_IN: 5,
    SPACING: 15,
    THUMBNAIL_SIZE: 50,
    POS: {
      TITLE: {
        row: 0,
        column: 0,
        colSpan: 4
      },
      THUMBNAIL: {
        row: 2,
        column: 0,
        colSpan: 4
      },
      AVATAR_GROUP: {
        row: 3,
        column: 0
      },
      TAGS: {
        row: 4,
        column: 0
      },
      FOOTER: {
        row: 5,
        column: 0,
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
        case "header": {
          const hGrid = new qx.ui.layout.Grid().set({
            spacing: 6,
          });
          hGrid.setRowFlex(0, 1);
          hGrid.setColumnFlex(1, 1);
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
          const fGrid = new qx.ui.layout.Grid();
          fGrid.setSpacing(2);
          fGrid.setColumnFlex(0, 1);
          control = new qx.ui.container.Composite().set({
            backgroundColor: "background-card-overlay",
            padding: this.self().PADDING - 2,
            maxWidth: this.self().ITEM_WIDTH,
            maxHeight: this.self().ITEM_HEIGHT
          });
          control.setLayout(fGrid);
          break;
        }
        case "icon": {
          control = osparc.dashboard.CardBase.createCardIcon();
          layout = this.getChildControl("header");
          layout.add(control, {
            column: 0,
            row: 0,
          });
          break;
        }
        case "title":
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-light",
            font: "text-14",
          });
          layout = this.getChildControl("header");
          layout.add(control, {
            column: 1,
            row: 0,
          });
          break;
        case "subtitle-icon": {
          control = new qx.ui.basic.Image().set({
            allowGrowX: false,
            allowShrinkX: false,
          });
          layout = this.getChildControl("header");
          layout.add(control, {
            column: 0,
            row: 1,
          });
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
          layout.add(control, {
            column: 1,
            row: 1,
          });
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

    __fitThumbnailHeight: function() {
      const thumbnailLayout = this.getChildControl("thumbnail");
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
      thumbnailLayout.getChildControl("image").setMaxHeight(maxHeight);
      thumbnailLayout.setMaxHeight(maxHeight);
      thumbnailLayout.recheckSize();
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
