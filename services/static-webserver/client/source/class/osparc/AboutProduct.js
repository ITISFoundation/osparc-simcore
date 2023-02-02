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

qx.Class.define("osparc.AboutProduct", {
  extend: osparc.ui.window.Window,
  type: "singleton",

  construct: function() {
    this.base(arguments, this.tr("About Product"));

    osparc.store.StaticInfo.getInstance().getDisplayName()
      .then(displayName => {
        this.setCaption(this.tr("About ") + displayName);
      });

    this.set({
      layout: new qx.ui.layout.VBox(5),
      minWidth: this.self().MIN_WIDTH,
      maxWidth: this.self().MAX_WIDTH,
      contentPadding: this.self().PADDING,
      showMaximize: false,
      showMinimize: false,
      resizable: false,
      centerOnAppear: true,
      clickAwayClose: true,
      modal: true
    });

    this.__buildLayout();
  },

  statics: {
    MIN_WIDTH: 200,
    MAX_WIDTH: 400,
    PADDING: 15
  },

  members: {
    __buildLayout: function() {
      const introText = new qx.ui.basic.Label().set({
        font: "text-14",
        maxWidth: this.self().MAX_WIDTH - 2*this.self().PADDING,
        rich: true,
        wrap: true
      });
      this.add(introText);
      osparc.store.StaticInfo.getInstance().getDisplayName()
        .then(displayName => {
          introText.setValue(displayName);
        });
    }
  }
});
