/** @odoo-module **/

import { registry } from "@web/core/registry";
import { BlockUI } from "@web/core/ui/block_ui";
import { download } from "@web/core/network/download";
import { useService } from "@web/core/utils/hooks";

const StockCardReport = {
    async setup(env, props) {
        this.env = env;
        this.props = props;
        this.context = props.context || {};
        this.model = this.context.active_model || false;
        this.active_id = this.context.active_id || false;
        this.controller_url = this.context.url || "";
        await this.loadHtml();
    },

    async loadHtml() {
        const result = await this.env.services.rpc({
            model: this.model,
            method: "get_html",
            args: [this.context],
            context: this.env.context,
        });
        this.html = result.html;
        this.renderHtml();
    },

    renderHtml() {
        const container = document.querySelector(".o_content");
        if (container) {
            container.innerHTML = this.html;
        }
    },

    async print() {
        const result = await this.env.services.rpc({
            model: this.model,
            method: "print_report",
            args: [this.active_id, "qweb-pdf"],
            context: this.env.context,
        });
        this.env.services.action.doAction(result);
    },

    async export() {
        const result = await this.env.services.rpc({
            model: this.model,
            method: "print_report",
            args: [this.active_id, "xlsx"],
            context: this.env.context,
        });
        this.env.services.action.doAction(result);
    },
};

// Register the backend action in the registry
registry.category("actions").add("stock_card_report_backend", (env, props) => {
    const instance = Object.create(StockCardReport);
    instance.setup(env, props);
    return instance;
});

// Register the XLSX report handler
registry.category("ir.actions.report handlers").add("stock_card_report_xlsx", async function (action) {
    if (action.report_type === "xlsx") {
        BlockUI;
//        try {
        await download({
            url: "/xlsx_reports",
            data: action.data,
            complete: () => unblockUI,
             error: (error) => self.call('crash_manager', 'rpc_error', error),
        });
//        } finally {
//            BlockUI.unblock();
//        }
    }
});
