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
      padding: this.self().PADDING,
      allowGrowX: false
    });

    this._setLayout(new qx.ui.layout.Canvas());

    const mainLayout = this._mainLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(this.self().V_SPACING)).set({
      maxWidth: this.self().ITEM_WIDTH - 2*this.self().PADDING,
      maxHeight: this.self().ITEM_HEIGHT - 2*this.self().PADDING
    });
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
    ICON_SIZE: 50,
    PADDING: 10,
    V_SPACING: 6,
    SPACING: 15,
    POS: {
      TITLE: 0,
      SUBTITLE: 1,
      THUMBNAIL: 2,
      TSR_MODE: 3,
      TAGS: 4
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
      let control;
      switch (id) {
        case "title":
          control = new qx.ui.basic.Label().set({
            margin: [5, 0],
            font: "title-14",
            maxWidth: this.self().ITEM_WIDTH - 2*this.self().PADDING,
            maxHeight: 34, // two lines
            rich: true,
            wrap: true,
            breakWithinWords: true
          });
          this._mainLayout.addAt(control, this.self().POS.TITLE);
          break;
        case "subtitle":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(6)).set({
            anonymous: true
          });
          this._mainLayout.addAt(control, this.self().POS.SUBTITLE);
          break;
        case "subtitle-icon": {
          control = new qx.ui.basic.Image();
          const sharedDescriptionLayout = this.getChildControl("subtitle");
          sharedDescriptionLayout.addAt(control, 0);
          break;
        }
        case "subtitle-text": {
          control = new qx.ui.basic.Label().set({
            anonymous: true,
            font: "text-13",
            allowGrowY: false
          });
          const sharedDescriptionLayout = this.getChildControl("subtitle");
          sharedDescriptionLayout.addAt(control, 1, {
            flex: 1
          });
          break;
        }
        case "icon": {
          const maxWidth = this.self().ITEM_WIDTH - 2*this.self().PADDING;
          control = new osparc.ui.basic.Thumbnail(null, maxWidth, 124);
          control.getChildControl("image").set({
            anonymous: true
          });
          this._mainLayout.addAt(control, this.self().POS.THUMBNAIL, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    // overridden
    _applyIcon: function(value, old) {
      if (value.includes("@FontAwesome5Solid/")) {
        value += this.self().ICON_SIZE;
      }
      const image = this.getChildControl("icon").getChildControl("image");
      image.set({
        source: value
      });

      [
        "appear",
        "loaded"
      ].forEach(eventName => {
        image.addListener(eventName, () => {
          this.__fitIconHeight();
        }, this);
      });
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
      let maxHeight = this.getHeight() - this.getPaddingTop() - this.getPaddingBottom();
      // eslint-disable-next-line no-underscore-dangle
      this._mainLayout._getChildren().forEach(child => {
        if (child.getSubcontrolId() !== "icon" && child.getBounds()) {
          maxHeight -= (child.getBounds().height + 6);
        }
      });
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
