/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.OrganizationListItem", {
  extend: osparc.dashboard.ServiceBrowserListItem,

  construct: function() {
    this.base(arguments);
  },

  properties: {
    accessRights: {
      check: "Object",
      nullable: false,
      event: "changeAcessRights"
    }
  }
});
