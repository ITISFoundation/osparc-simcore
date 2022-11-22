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

qx.Class.define("osparc.component.widget.SlideBar", {
  extend: qx.ui.container.SlideBar,

  construct: function() {
    this.base(arguments);

    this.setLayout(new qx.ui.layout.HBox(0));

    this.__pimpButtons();
  },

  members: {
    __pimpButtons: function() {
      const buttonBackward = this.getChildControl("button-backward");
      const buttonForward = this.getChildControl("button-forward");
      [
        buttonBackward,
        buttonForward
      ].forEach(button => {
        button.set({
          alignY: "middle",
          opacity: 0.6,
          backgroundColor: "background-main-2",
          allowGrowY: true
        });
      });
      buttonBackward.setIcon("@FontAwesome5Solid/chevron-left/16");
      buttonForward.setIcon("@FontAwesome5Solid/chevron-right/16");
    },

    setScrollButtonsWidth: function(width) {
      const buttonBackward = this.getChildControl("button-backward");
      buttonBackward.set({
        width
      });
      const buttonForward = this.getChildControl("button-forward");
      buttonForward.set({
        width
      });
    }
  }
});
