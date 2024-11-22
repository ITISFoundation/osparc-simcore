/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* eslint "qx-rules/no-refs-in-members": "warn" */

/**
 * Widget used mainly by ServiceBrowser for displaying service related information
 *
 *   It consists of a key as title, and name and contact as caption
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   tree.setDelegate({
 *     createItem: () => new osparc.ui.list.ListItem(),
 *     bindItem: (c, item, id) => {
 *       c.bindProperty("key", "model", null, item, id);
 *       c.bindProperty("thumbnail", "thumbnail", null, item, id);
 *       c.bindProperty("name", "title", null, item, id);
 *       c.bindProperty("description", "subtitle", null, item, id);
 *       c.bindProperty("role", "role", null, item, id);
 *     }
 *   });
 * </pre>
 */

qx.Class.define("osparc.ui.list.ListItem", {
  extend: qx.ui.core.Widget,
  implement : [qx.ui.form.IModel, osparc.filter.IFilterable],
  include : [qx.ui.form.MModelProperty, osparc.filter.MFilterable],

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid(8, 1);
    layout.setColumnWidth(0, 32);
    layout.setRowFlex(0, 1);
    layout.setColumnFlex(1, 1);
    layout.setColumnAlign(0, "center", "middle");
    layout.setColumnAlign(2, "center", "middle");
    this._setLayout(layout);

    this.set({
      padding: 5,
      minHeight: 48,
      alignY: "middle",
    });

    this.addListener("pointerover", this._onPointerOver, this);
    this.addListener("pointerout", this._onPointerOut, this);
  },

  events: {
    /** (Fired by {@link qx.ui.form.List}) */
    "action" : "qx.event.type.Event"
  },

  properties: {
    appearance: {
      refine : true,
      init : "selectable"
    },

    key: {
      check: "String",
      apply : "__applyKey"
    },

    thumbnail: {
      check : "String",
      apply : "_applyThumbnail",
      nullable : true
    },

    title: {
      check : "String",
      apply : "__applyTitle",
      nullable : true
    },

    subtitle: {
      check : "String",
      apply : "__applySubtitle",
      nullable : true
    },

    subtitleMD: {
      check : "String",
      apply : "_applySubtitleMD",
      nullable : true
    },

    role: {
      check : "String",
      apply : "__applyRole",
      nullable : true
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

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "thumbnail":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            scale: true,
            allowGrowX: true,
            allowGrowY: true,
            allowShrinkX: true,
            allowShrinkY: true,
            maxWidth: 32,
            maxHeight: 32
          });
          this._add(control, {
            row: 0,
            column: 0,
            rowSpan: 2
          });
          break;
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: 1
          });
          break;
        case "subtitle":
          control = new qx.ui.basic.Label().set({
            font: "text-13",
            rich: true
          });
          this._add(control, {
            row: 1,
            column: 1
          });
          break;
        // or
        case "subtitle-md":
          control = new osparc.ui.markdown.Markdown().set({
            font: "text-13",
            noMargin: true,
            maxHeight: 18
          });
          this._add(control, {
            row: 1,
            column: 1
          });
          break;
        case "role":
          control = new qx.ui.basic.Label().set({
            font: "text-13",
            alignY: "middle"
          });
          this._add(control, {
            row: 0,
            column: 2,
            rowSpan: 2
          });
          break;
      }
      if (control) {
        control.set({
          anonymous: true
        });
      }

      return control || this.base(arguments, id);
    },

    __applyKey: function(value, old) {
      if (value === null) {
        return;
      }
      const parts = value.split("/");
      const id = parts.pop();
      if (osparc.utils.Utils.getIdFromWidget(this) === null) {
        osparc.utils.Utils.setIdToWidget(this, "listItem_"+id);
      }
    },

    _applyThumbnail: function(value) {
      if (value === null) {
        return;
      }
      const thumbnail = this.getChildControl("thumbnail");
      thumbnail.setSource(value);
    },

    __applyTitle: function(value) {
      if (value === null) {
        return;
      }
      const label = this.getChildControl("title");
      label.setValue(value);
    },

    __applySubtitle: function(value) {
      if ([null, undefined, ""].includes(value)) {
        return;
      }
      const label = this.getChildControl("subtitle");
      label.setValue(value);
    },

    _applySubtitleMD: function(value) {
      if ([null, undefined, ""].includes(value)) {
        return;
      }
      const label = this.getChildControl("subtitle-md");
      label.setValue(value);
    },

    __applyRole: function(value) {
      if (value === null) {
        return;
      }
      const label = this.getChildControl("role");
      label.setValue(value);
    },

    /**
     * Event handler for filtering events.
     */
    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        const checks = [
          this.getTitle(),
          this.getSubtitle(),
          this.getSubtitleMD()
        ];
        if (checks.filter(check => check && check.toLowerCase().trim().includes(data.text)).length == 0) {
          return true;
        }
      }
      return false;
    },

    _shouldReactToFilter: function(data) {
      if (data.text && data.text.length > 1) {
        return true;
      }
      return false;
    }
  }
});
