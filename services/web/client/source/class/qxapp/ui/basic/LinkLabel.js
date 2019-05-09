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

/**
 * A Label with low optical impact presenting as a simple weblink
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const link = new qxapp.ui.basic.LinkLabel(this.tr("oSparc"),"https://osparc.io");
 *   this.getRoot().add(link);
 * </pre>
 */

qx.Class.define("qxapp.ui.basic.LinkLabel", {
  extend: qx.ui.basic.Label,

  construct: function(label, url) {
    this.base(arguments, "<u>"+label+"</u>");

    this.set({
      rich: true,
      cursor: "pointer",
      url: url
    });

    this.addListener("click", this._onClick);
  },

  properties: {
    url: {
      check: "String",
      nullable: true
    }
  },

  members: {
    _onClick: function(e) {
      window.open(this.getUrl());
    }
  }
});
