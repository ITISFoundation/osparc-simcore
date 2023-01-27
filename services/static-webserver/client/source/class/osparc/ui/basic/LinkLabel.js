/* ************************************************************************

   osparc - the simcore frontend

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
 *   const link = new osparc.ui.basic.LinkLabel(this.tr("oSparc"),"https://osparc.io");
 *   this.getRoot().add(link);
 * </pre>
 */

qx.Class.define("osparc.ui.basic.LinkLabel", {
  extend: qx.ui.basic.Label,

  construct: function(label, url) {
    this.base(arguments, label);

    this.set({
      rich: true,
      allowGrowX: true
    });

    if (url) {
      this.setUrl(url);
    }
  },

  properties: {
    url: {
      check: "String",
      nullable: true,
      apply: "__applyUrl"
    }
  },

  members: {
    __applyUrl: function(url) {
      this.set({
        url,
        cursor: "pointer",
        font: "link-label"
      });

      this.addListener("click", this.__onClick);
    },

    __onClick: function() {
      const link = this.getUrl();
      if (link) {
        window.open(link);
      }
    }
  }
});
