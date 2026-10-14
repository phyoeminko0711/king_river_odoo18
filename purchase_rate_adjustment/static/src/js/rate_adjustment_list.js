/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";

class RateAdjustmentHistoryListController extends ListController {
    async openWizard() {
        return this.actionService.doAction(
            "purchase_rate_adjustment.action_purchase_rate_adjustment_wizard",
            {
                onClose: async () => this.model.root.load(),
            }
        );
    }

    async openRecord() {
        // History is intentionally available as a list only.
    }
}

registry.category("views").add("purchase_rate_adjustment_history_list", {
    ...listView,
    Controller: RateAdjustmentHistoryListController,
    buttonTemplate: "purchase_rate_adjustment.HistoryButtons",
});
