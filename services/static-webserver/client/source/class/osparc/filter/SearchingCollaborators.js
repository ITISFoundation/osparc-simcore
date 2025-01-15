/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2025 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.filter.SearchingCollaborators", {
  extend: qx.ui.basic.Atom,

  construct: function() {
    this.base(arguments);

    this.set({
      label: this.tr("Searching..."),
      icon: "@FontAwesome5Solid/circle-notch/14",
      appearance: "tagbutton",
      gap: 10,
    });

    this.getChildControl("icon").getContentElement().addClass("rotate");
    this.getChildControl("label").setTextColor("text");
  },
});
