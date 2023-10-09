/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Based on the double column renderer for {@link qx.ui.form.Form}.
 * This custom class shows the buddy over the field and supports fields taking the double space
 */
qx.Class.define("osparc.ui.form.renderer.DoubleV", {
  extend: qx.ui.form.renderer.AbstractRenderer,

  construct: function(form, doubleSpacedNames) {
    const layout = new qx.ui.layout.Grid();
    layout.setSpacing(15);
    layout.setColumnAlign(0, "left", "bottom");
    layout.setColumnAlign(1, "left", "bottom");
    this._setLayout(layout);

    this.__doubleSpacedNames = doubleSpacedNames || [];

    this.base(arguments, form);
  },

  members: {
    __doubleSpacedNames: null,
    __row: 0,
    __buttonRow: null,

    // overridden
    _onFormChange : function() {
      if (this.__buttonRow) {
        this.__buttonRow.destroy();
        this.__buttonRow = null;
      }
      this.__row = 0;
      this.base(arguments);
    },

    /**
     * Add a group of form items with the corresponding names. The names are
     * displayed as label.
     * The title is optional and is used as grouping for the given form
     * items.
     *
     * @param items {qx.ui.core.Widget[]} An array of form items to render.
     * @param names {String[]} An array of names for the form items.
     * @param title {String?} A title of the group you are adding.
     */
    addItems : function(items, names, title) {
      // add the header
      if (title != null) {
        this._add(this._createHeader(title), {
          row: this.__row,
          column: 0,
          colSpan: 2
        });
        this.__row++;
      }

      // add the items
      let i = 0;
      let col = 0;
      for (; i < items.length; i++) {
        const name = names[i];
        const item = items[i];
        const takeDouble = this.__doubleSpacedNames.includes(item);

        const itemLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());
        const label = this._createLabel(name, item).set({
          font: "text-12"
        });
        label.setBuddy(item);
        itemLayout.add(label);
        item.setBackgroundColor("transparent");
        itemLayout.add(item);
        this._add(itemLayout, {
          row: this.__row,
          column: takeDouble ? 0 : col,
          colSpan: takeDouble ? 2 : 1
        });

        this._connectVisibility(item, label);

        if (takeDouble || col === 1) {
          col = 0;
          this.__row++;
        } else {
          col = 1;
        }

        // store the names for translation
        if (qx.core.Environment.get("qx.dynlocale")) {
          this._names.push({
            name,
            label,
            item
          });
        }
      }

      if (i % 2 == 1) {
        this.__row++;
      }
    },

    /**
     * Adds a button the form renderer. All buttons will be added in a
     * single row at the bottom of the form.
     *
     * @param button {qx.ui.form.Button} The button to add.
     */
    addButton : function(button) {
      if (this.__buttonRow == null) {
        // create button row
        this.__buttonRow = new qx.ui.container.Composite();
        this.__buttonRow.setMarginTop(5);
        const hBox = new qx.ui.layout.HBox();
        hBox.setAlignX("right");
        hBox.setSpacing(5);
        this.__buttonRow.setLayout(hBox);
        // add the button row
        this._add(this.__buttonRow, {
          row: this.__row,
          column: 0,
          colSpan: 2
        });
        // increase the row
        this.__row++;
      }

      // add the button
      this.__buttonRow.add(button);
    },

    /**
     * Returns the set layout for configuration.
     *
     * @return {qx.ui.layout.Grid} The grid layout of the widget.
     */
    getLayout : function() {
      return this._getLayout();
    },

    /**
     * Creates a label for the given form item.
     *
     * @param name {String} The content of the label without the
     *   trailing * and :
     * @param item {qx.ui.core.Widget} The item, which has the required state.
     * @return {qx.ui.basic.Label} The label for the given item.
     */
    _createLabel: function(name, item) {
      const label = new qx.ui.basic.Label(this._createLabelText(name, item));
      // store labels for disposal
      this._labels.push(label);
      label.setRich(true);
      return label;
    },

    /**
     * Creates a header label for the form groups.
     *
     * @param title {String} Creates a header label.
     * @return {qx.ui.basic.Label} The header for the form groups.
     */
    _createHeader : function(title) {
      const header = new qx.ui.basic.Label(title);
      // store labels for disposal
      this._labels.push(header);
      header.setFont("bold");
      if (this.__row != 0) {
        header.setMarginTop(10);
      }
      header.setAlignX("left");
      return header;
    }
  },

  /*
  *****************************************************************************
     DESTRUCTOR
  *****************************************************************************
  */
  destruct : function() {
    // first, remove all buttons from the bottom row because they
    // should not be disposed
    if (this.__buttonRow) {
      this.__buttonRow.removeAll();
      this._disposeObjects("__buttonRow");
    }
  }
});
