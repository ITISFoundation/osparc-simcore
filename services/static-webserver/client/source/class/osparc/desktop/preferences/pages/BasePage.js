/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.preferences.pages.BasePage", {
  extend: qx.ui.tabview.Page,

  construct: function(title, iconSrc = null) {
    this.base(arguments, null, iconSrc);

    this.setLayout(new qx.ui.layout.VBox(10));

    this.set({
      backgroundColor: "window-popup-background",
      paddingTop: 5,
      paddingLeft: 15
    });

    this.__showLabelOnTab(title);

    const tabButton = this.getChildControl("button");
    if (tabButton.getIcon() && tabButton.getIcon().includes(".svg")) {
      tabButton.getChildControl("icon").set({
        minWidth: 24,
        minHeight: 24,
        scale: true,
      });
      osparc.ui.basic.SVGImage.setColorToImage(tabButton.getChildControl("icon"), "text");
    }
  },

  members: {
    __showLabelOnTab: function(title) {
      const tabButton = this.getChildControl("button");
      tabButton.set({
        label: title,
        font: "text-14"
      });
      // eslint-disable-next-line no-underscore-dangle
      const buttonLayout = tabButton._getLayout();
      buttonLayout.setColumnAlign(0, "center", "middle"); // center icon
      buttonLayout.setColumnWidth(0, 24); // align texts
      buttonLayout.setSpacingX(5);
    }
  }
});
