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
 * Big button with a title, a text, an icon, and a footer text.
 */
qx.Class.define("osparc.ui.form.Jumbo", {
  extend: qx.ui.form.ToggleButton,

  /**
   * Constructor of the Jumbo button.
   *
   * @param {String} label This is the title of the button, shown on top with bigger font.
   * @param {String} text This is the middle text. It adds more information.
   * @param {String} icon Id of the icon that will show to the right of the title (label).
   * @param {String} footer Text that shows on the bottom left of the button, in small font.
   */
  construct: function(label, text, icon, footer) {
    this.base(arguments, label, icon);

    this.set({
      width: 180,
      height: 90
    });

    if (text != null) {
      this.setText(text);
    }
    if (footer != null) {
      this.setFooter(footer);
    }
  },

  properties: {
    appearance: {
      refine: true,
      init: "jumbo"
    },
    text: {
      nullable: true,
      check: "String",
      apply: "_applyText"
    },
    footer: {
      nullable: true,
      check: "String",
      apply: "_applyFooter"
    }
  },

  members: {
    __layout: null,
    _createChildControlImpl: function(id) {
      let control;
      if (this.__layout === null) {
        this.__layout = new qx.ui.layout.Grid(0, 5);
        this.__layout.setRowFlex(1, 1);
        this.__layout.setColumnFlex(0, 1);
        this._setLayout(this.__layout);
      }
      switch (id) {
        case "label":
          control = new qx.ui.basic.Label(this.getLabel()).set({
            font: "title-14",
            rich: true,
            anonymous: true
          });
          this._add(control, {
            row: 0,
            column: 0
          });
          break;
        case "icon":
          control = new qx.ui.basic.Image(this.getIcon()).set({
            anonymous: true
          });
          this._add(control, {
            row: 0,
            column: 1
          });
          break;
        case "text":
          control = new qx.ui.basic.Label(this.getText()).set({
            rich: true,
            font: "text-12-italic",
            anonymous: true
          });
          this._add(control, {
            row: 1,
            column: 0,
            colSpan: 2
          });
          break;
        case "footer":
          control = new qx.ui.basic.Label(this.getFooter()).set({
            font: "text-10",
            anonymous: true
          });
          this._add(control, {
            row: 2,
            column: 0,
            colSpan: 2
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    _applyText: function(value) {
      const text = this.getChildControl("text");
      if (text) {
        text.setValue(value);
      }
    },

    _applyFooter: function(value) {
      const footer = this.getChildControl("footer");
      if (footer) {
        footer.setValue(value);
      }
    }
  }
});
