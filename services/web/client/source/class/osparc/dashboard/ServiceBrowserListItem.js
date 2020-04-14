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
 *     createItem: () => new osparc.dashboard.ServiceBrowserListItem(),
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

qx.Class.define("osparc.dashboard.ServiceBrowserListItem", {
  extend: qx.ui.core.Widget,
  implement : [qx.ui.form.IModel, osparc.component.filter.IFilterable],
  include : [qx.ui.form.MModelProperty, osparc.component.filter.MFilterable],

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

    key: {
      check: "String",
      apply : "_applyKey"
    },

    version: {
      check: "String"
    },

    dagId: {
      check : "String",
      nullable : true
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
          control = new qx.ui.basic.Label().set({
            font: osparc.utils.Utils.getFont(14, true)
          });
          this._add(control, {
            row: 0,
            column: 0
          });
          break;
        case "description":
          control = new osparc.ui.markdown.Markdown().set({
            maxHeight: 16
          });
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

    _applyKey: function(value, old) {
      if (value === null) {
        return;
      }
      const parts = value.split("/");
      const id = parts.pop();
      osparc.utils.Utils.setIdToWidget(this, "serviceBrowserListItem_"+id);
    },

    _applyTitle: function(value) {
      if (value === null) {
        return;
      }
      const label = this.getChildControl("title");
      label.setValue(value);
    },

    _applyDescription: function(value) {
      if (value === null) {
        return;
      }
      const label = this.getChildControl("description");
      label.setValue(value);
    },

    _applyContact: function(value) {
      if (value === null) {
        return;
      }
      const label = this.getChildControl("contact");
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
      if (data.text && this.getTitle()) {
        const label = this.getTitle()
          .trim()
          .toLowerCase();
        if (label.indexOf(data.text) === -1) {
          return true;
        }
      }
      if (data.tags && data.tags.length && this.getCategory()) {
        const category = this.getCategory() || "";
        const type = this.getType() || "";
        if (!data.tags.includes(osparc.utils.Utils.capitalize(category.trim())) && !data.tags.includes(osparc.utils.Utils.capitalize(type.trim()))) {
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
