/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * TextField to make a simple text filter.
 */
qx.Class.define("osparc.filter.TextFilter", {
  extend: osparc.filter.UIFilter,

  /**
   * Constructor for the TextFilter takes UIFilters mandatory params plus an optional translation id for its label.
   *
   * @extends osparc.filter.UIFilter
   */
  construct: function(filterId, filterGroupId) {
    this.base(arguments, filterId, filterGroupId);
    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      allowStretchX: false,
      allowStretchY: false
    });

    this.getChildControl("textfield");
    this.getChildControl("clearbutton");

    this.__attachEventHandlers();
  },

  properties: {
    appearance: {
      refine: true,
      init: "textfilter"
    },

    compact: {
      check: "Boolean",
      init: false,
      apply: "__applyCompact",
    },
  },

  members: {
    /**
     * Function that resets the field and dispatches the update.
     */
    reset: function() {
      const textField = this.getChildControl("textfield");
      textField.resetValue();
      textField.fireDataEvent("input", "");
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "textfield":
          control = new qx.ui.form.TextField().set({
            paddingRight: 15,
            placeholder: this.tr("Filter")
          });
          osparc.utils.Utils.disableAutocomplete(control);
          this._add(control, {
            width: "100%"
          });
          break;
        case "clearbutton":
          control = new osparc.ui.basic.IconButton("@MaterialIcons/close/12", () => {
            this.reset();
            this.getChildControl("textfield").focus();
          });
          this._add(control, {
            right: 0,
            bottom: 6
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyCompact: function(compact) {
      this.set({
        allowStretchX: compact,
        allowGrowX: compact,
        maxHeight: compact ? 30 : null,
        margin: compact ? 0 : null,
      });

      this.getChildControl("textfield").set({
        margin: compact ? 0 : null,
      });
    },

    __attachEventHandlers: function() {
      this.getChildControl("textfield").addListener("input", evt => {
        this._filterChange(evt.getData().trim().toLowerCase());
      });
    }
  }
});
