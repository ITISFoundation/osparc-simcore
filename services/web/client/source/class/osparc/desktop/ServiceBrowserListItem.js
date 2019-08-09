/* ************************************************************************

   qxapp - the simcore frontend

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
 *     createItem: () => new qxapp.desktop.ServiceBrowserListItem(),
 *     bindItem: (c, item, id) => {
 *       c.bindProperty("key", "model", null, item, id);
 *       c.bindProperty("name", "title", null, item, id);
 *       c.bindProperty("description", "description", null, item, id);
 *       c.bindProperty("type", "type", null, item, id);
 *       c.bindProperty("category", "category", null, item, id);
 *       c.bindProperty("contact", "contact", null, item, id);
 *     }
 *   });
 * </pre>
 */

qx.Class.define("qxapp.desktop.ServiceBrowserListItem", {
  extend: qx.ui.core.Widget,
  implement : [qx.ui.form.IModel, qxapp.component.filter.IFilterable],
  include : [qx.ui.form.MModelProperty, qxapp.component.filter.MFilterable],

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid(0, 5);
    layout.setColumnFlex(0, 1);
    this._setLayout(layout);
    this.setPadding(5);

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

    title: {
      check : "String",
      apply : "_applyTitle",
      nullable : true
    },

    description: {
      check : "String",
      apply : "_applyDescription",
      nullable : true
    },

    type: {
      check : "String",
      nullable : true
    },

    contact: {
      check : "String",
      apply : "_applyContact",
      nullable : true
    },

    category: {
      check : "String",
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
        case "title":
          control = new qxapp.ui.basic.Label(14, true);
          this._add(control, {
            row: 0,
            column: 0
          });
          break;
        case "description":
          control = new qx.ui.basic.Label();
          this._add(control, {
            row: 1,
            column: 0
          });
          break;
        case "contact":
          control = new qx.ui.basic.Label().set({
            font: "text-12"
          });
          this._add(control, {
            row: 1,
            column: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    _applyTitle: function(value) {
      const label = this.getChildControl("title");
      label.setValue(value);
    },

    _applyDescription: function(value) {
      const label = this.getChildControl("description");
      label.setValue(value);
    },

    _applyContact: function(value) {
      const label = this.getChildControl("contact");
      label.setValue(value);
    },

    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        const label = this.getTitle()
          .trim()
          .toLowerCase();
        if (label.indexOf(data.text) === -1) {
          return true;
        }
      }
      if (data.tags && data.tags.length) {
        const category = this.getCategory() || "";
        const type = this.getType() || "";
        if (!data.tags.includes(category.trim().toLowerCase()) && !data.tags.includes(type.trim().toLowerCase())) {
          return true;
        }
      }
      return false;
    },

    _shouldReactToFilter: function(data) {
      if (data.text && data.text.length > 1) {
        return true;
      }
      if (data.tags && data.tags.length) {
        return true;
      }
      return false;
    }
  }
});
