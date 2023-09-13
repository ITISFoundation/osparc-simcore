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

/*
 * A SlideBar that has the backward/forward buttons ON the content container.
 * Some transparency is given to the buttons to make the background container still visible.
 */

qx.Class.define("osparc.widget.SlideBar", {
  extend: qx.ui.container.SlideBar,

  construct: function(spacing) {
    this.base(arguments);

    const layout = new qx.ui.layout.HBox(spacing? spacing : 5);
    this.setLayout(layout);

    this.__pimpLayout();
  },

  properties: {
    buttonsWidth: {
      check: "Integer",
      init: 30,
      nullable: false,
      apply: "__updateElementSizes"
    }
  },

  members: {
    __pimpLayout: function() {
      const buttonBackward = this.getChildControl("button-backward");
      const buttonForward = this.getChildControl("button-forward");
      [
        buttonBackward,
        buttonForward
      ].forEach(button => {
        button.set({
          alignY: "middle",
          opacity: 0.7,
          backgroundColor: "background-main",
          allowGrowY: true
        });
      });
      buttonBackward.setIcon("@FontAwesome5Solid/chevron-left/16");
      buttonBackward.getContentElement().setStyles({
        "border-top-left-radius": "0px",
        "border-bottom-left-radius": "0px"
      });
      buttonForward.setIcon("@FontAwesome5Solid/chevron-right/16");
      buttonForward.getContentElement().setStyles({
        "border-top-right-radius": "0px",
        "border-bottom-right-radius": "0px"
      });
    },

    // override
    _onResize: function() {
      this.base(arguments);
      this.__updateElementSizes();
    },

    __updateElementSizes: function() {
      const btnWidth = this.getButtonsWidth();
      const contentPane = this.getChildControl("scrollpane");
      const padding = 3;
      contentPane.set({
        marginLeft: -btnWidth + padding,
        marginRight: -btnWidth + padding
      });
      const size = this.getInnerSize();
      if (size) {
        this.set({
          scrollStep: size.width
        });
      }
      const buttonBackward = this.getChildControl("button-backward");
      const buttonForward = this.getChildControl("button-forward");
      [
        buttonBackward,
        buttonForward
      ].forEach(button => {
        button.getChildControl("icon").set({
          opacity: 1
        });
      });
    },

    // override
    _updateArrowsEnabled: function() {
      this.base(arguments);

      const buttonBackward = this.getChildControl("button-backward");
      const buttonForward = this.getChildControl("button-forward");
      [
        buttonBackward,
        buttonForward
      ].forEach(button => {
        button.setVisibility(button.getEnabled() ? "visible" : "hidden");
      });
    }
  }
});
