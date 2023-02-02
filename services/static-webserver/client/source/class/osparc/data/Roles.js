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


qx.Class.define("osparc.data.Roles", {
  type: "static",

  statics: {
    ORG: {
      0: {
        id: "noRead",
        label: qx.locale.Manager.tr("User"),
        longLabel: qx.locale.Manager.tr("User: no Read access"),
        canDo: [
          qx.locale.Manager.tr("- can access content shared within the Organization")
        ]
      },
      1: {
        id: "read",
        label: qx.locale.Manager.tr("Member"),
        longLabel: qx.locale.Manager.tr("Member: Read access"),
        canDo: [
          qx.locale.Manager.tr("- can See other members"),
          qx.locale.Manager.tr("- can Share with other members")
        ]
      },
      2: {
        id: "write",
        label: qx.locale.Manager.tr("Manager"),
        longLabel: qx.locale.Manager.tr("Manager: Read/Write access"),
        canDo: [
          qx.locale.Manager.tr("- can Add/Delete members"),
          qx.locale.Manager.tr("- can Promote/Demote members"),
          qx.locale.Manager.tr("- can Edit Organization details")
        ]
      },
      3: {
        id: "delete",
        label: qx.locale.Manager.tr("Administrator"),
        longLabel: qx.locale.Manager.tr("Admin: Read/Write/Delete access"),
        canDo: [
          qx.locale.Manager.tr("- can Delete the Organization")
        ]
      }
    }
  }
});
