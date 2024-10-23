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
      padding: 0
    });

    this._setLayout(new qx.ui.layout.Canvas());

    this.getChildControl("main-layout");

    [
      "pointerover",
      "focus"
    ].forEach(e => this.addListener(e, this._onPointerOver, this));

    [
      "pointerout",
      "focusout"
    ].forEach(e => this.addListener(e, this._onPointerOut, this));
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
    SPACING: 15,
    HEADER_MAX_HEIGHT: 44,
    ICON_SIZE: 60,
    POS: {
      FOLDER_LOOK: 0,
      HEADER: 1,
      BODY: 2,
      FOOTER: 3
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

  events: {
    /** (Fired by {@link qx.ui.form.List}) */
    "action": "qx.event.type.Event"
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
          control = new qx.ui.container.Composite();
          const folderLook = this.getChildControl("folder-look");
          const header = this.getChildControl("header");
          const body = this.getChildControl("body");
          const footer = this.getChildControl("footer");
          control.addAt(folderLook, this.self().POS.FOLDER_LOOK);
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
        case "folder-look": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox()).set({
            backgroundColor: "background-main",
            maxHeight: 8,
          });
          const spacer = new qx.ui.core.Widget().set({
            backgroundColor: "background-workspace-card-overlay"
          });
          spacer.getContentElement().setStyles({
            "border-top-right-radius": "6px",
          });
          const spacer2 = new qx.ui.core.Widget();
          control.add(spacer, {flex: 1});
          control.add(spacer2, {flex: 1});
          break;
        }
        case "header":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
            backgroundColor: "background-workspace-card-overlay",
            opacity: 0.8,
            anonymous: true,
            maxWidth: this.self().ITEM_WIDTH,
            maxHeight: this.self().HEADER_MAX_HEIGHT,
            padding: this.self().PADDING,
            alignY: "middle",
          });
          break;
        case "body":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
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
            allowGrowX: true,
            alignY: "middle",
            maxHeight: this.self().HEADER_MAX_HEIGHT
          });
          layout = this.getChildControl("header");
          layout.addAt(control, this.self().HPOS.TITLE, {
            flex: 1
          });
          break;
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
      }
      return control || this.base(arguments, id);
    },

    // overridden
    _applyIcon: function(value) {
      const image = this.getChildControl("icon").getChildControl("image");
      if (
        value.includes("@FontAwesome5Solid/") ||
        value.includes("@MaterialIcons/")
      ) {
        this.getContentElement().setStyles({
          "background-image": "none",
        });
        value += this.self().ICON_SIZE;
        image.set({
          source: value,
          visibility: "visible",
        });
      } else {
        this.getContentElement().setStyles({
          "background-image": `url(${value})`,
          "background-repeat": "no-repeat",
          "background-size": "cover", // auto width, 85% height
          "background-position": "center center",
          "background-origin": "border-box"
        });
        image.set({
          visibility: "excluded",
        });
      }
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

    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _shouldApplyFilter: function(data) {
      return false;
    },

    _shouldReactToFilter: function(data) {
      return false;
    }
  },

  destruct: function() {
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
