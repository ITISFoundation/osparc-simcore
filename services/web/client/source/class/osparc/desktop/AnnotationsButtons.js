/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * <pre class='javascript'>
 *   let annotationsButtons = new osparc.desktop.AnnotationsButtons();
 *   this.getRoot().add(annotationsButtons);
 * </pre>
 */

qx.Class.define("osparc.desktop.AnnotationsButtons", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    this.__initLayout();
  },

  events: {
    "startRect": "qx.event.type.Event",
    "stopRect": "qx.event.type.Event",
    "startText": "qx.event.type.Event",
    "stopText": "qx.event.type.Event"
  },

  members: {
    __rectButton: null,
    __textButton: null,

    __initLayout: function() {
      const buttons = new qx.ui.toolbar.Part();

      const rectButton = this.__rectButton = new qx.ui.toolbar.RadioButton().set({
        value: false,
        icon: "@FontAwesome5Solid/paw/14",
        toolTipText: this.tr("Draw Rectangle")
      });
      rectButton.addListener("changeValue", e => this.fireEvent(e.getData() ? "startRect" : "stopRect"), this);
      buttons.add(rectButton);

      const textButton = this.__textButton = new qx.ui.toolbar.RadioButton().set({
        value: false,
        icon: "@FontAwesome5Solid/paw/14",
        toolTipText: this.tr("Insert Text")
      });
      textButton.addListener("changeValue", e => this.fireEvent(e.getData() ? "startText" : "stopText"), this);
      buttons.add(textButton);

      const radioGroup = new qx.ui.form.RadioGroup(rectButton, textButton);
      radioGroup.setAllowEmptySelection(true);

      this._add(buttons);
    }
  }
});
