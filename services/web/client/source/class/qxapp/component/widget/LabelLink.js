/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("qxapp.component.widget.LabelLink", {
  extend: qx.ui.basic.Label,

  construct: function(label, url) {
    this.base(arguments, "<u>"+label+"</u>");

    this.set({
      rich: true,
      cursor: "pointer",
      url: url
    });

    this.addListener("tap", this._onTap);
  },

  properties: {
    url: {
      check: "String",
      nullable: true
    }
  },

  members: {
    _onTap: function() {
      window.open(this.getUrl());
    }
  }
});
