/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.WorkspaceButtonBase", {
  extend: qx.ui.form.ToggleButton,
  implement: [qx.ui.form.IModel, osparc.filter.IFilterable],
  include: [qx.ui.form.MModelProperty, osparc.filter.MFilterable],
  type: "abstract",

  construct: function() {
    this.base(arguments);

    this.set({
      width: this.self().ITEM_WIDTH,
      height: this.self().ITEM_HEIGHT,
      padding: 5,
      alignY: "middle"
    });

    this._setLayout(new qx.ui.layout.Canvas());

    this.getChildControl("main-layout");

    this.addListener("pointerover", this._onPointerOver, this);
    this.addListener("pointerout", this._onPointerOut, this);
  },

  properties: {
    cardKey: {
      check: "String",
      nullable: true
    },

    resourceType: {
      check: ["workspace"],
      init: "workspace",
      nullable: false
    },

    priority: {
      check: "Number",
      init: null,
      nullable: false
    }
  },

  statics: {
    ITEM_WIDTH: 190,
    ITEM_HEIGHT: 190,
    PADDING: 10,
    SPACING_IN: 5,
    SPACING: 15,
    HEADER_MAX_HEIGHT: 40, // two lines in Manrope
    POS: {
      HEADER: 0,
      BODY: 1,
      FOOTER: 2
    },
    HPOS: {
      SHARED: 0,
      TITLE: 1,
      MENU: 2,
    },
    FPOS: {
      MODIFIED: 0
    }
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
    // overridden
    _forwardStates: {
      focused : true,
      hovered : true,
      selected : true,
      dragover : true
    },

    // overridden
    _createChildControlImpl: function(id) {
      let layout;
      let control;
      switch (id) {
        case "main-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(this.self().SPACING_IN));
          const header = this.getChildControl("header");
          const body = this.getChildControl("body");
          const footer = this.getChildControl("footer");
          control.addAt(header, this.self().POS.HEADER);
          control.addAt(body, this.self().POS.BODY, {
            flex: 1
          });
          control.addAt(footer, this.self().POS.FOOTER);
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
        }
        case "header":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
            backgroundColor: "background-card-overlay",
            anonymous: true,
            maxWidth: this.self().ITEM_WIDTH,
            maxHeight: this.self().HEADER_MAX_HEIGHT,
            padding: this.self().PADDING,
            alignY: "middle",
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
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
            backgroundColor: "background-card-overlay",
            anonymous: true,
            maxWidth: this.self().ITEM_WIDTH,
            maxHeight: this.self().ITEM_HEIGHT,
            padding: this.self().PADDING,
            alignY: "middle",
          });
          break;
        }
        case "title":
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-light",
            font: "text-14",
            maxWidth: this.self().ITEM_WIDTH - 2*this.self().PADDING,
            maxHeight: this.self().HEADER_MAX_HEIGHT
          });
          layout = this.getChildControl("header");
          layout.addAt(control, this.self().HPOS.TITLE, {
            flex: 1
          });
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

    _onPointerOver: function() {
      this.addState("hovered");
    },

    _onPointerOut : function() {
      this.removeState("hovered");
    },

    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _shouldApplyFilter: function(data) {
      console.log("_shouldApplyFilter", data);
      return false;
    },

    _shouldReactToFilter: function(data) {
      console.log("_shouldReactToFilter", data);
      return false;
    }
  },

  destruct: function() {
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
