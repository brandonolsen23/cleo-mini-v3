import { useState } from "react";
import {
    Icon,
    Button,
    Card,
    Search,
    Percentage,
    Tabs,
    Field,
    Tooltip,
    Checkbox,
    Switch,
    Select,
    Modal,
    Dropdown,
    Table,
    TableRow,
    Spinner,
    Image,
} from "../core2";

const iconNames = [
    "add-circle", "arrow", "arrow-down", "arrow-right", "arrow-up", "arrow-left",
    "ban", "calendar", "chart", "check", "chevron", "clock", "close", "cube",
    "dashboard", "dots", "emoji", "filters", "grid", "heart", "help", "home",
    "info", "layers", "lock", "notification", "plus", "product", "profile",
    "promote", "search", "send", "settings", "star-stroke", "star-fill",
    "trash", "upload", "video", "wallet",
];

const selectOptions = [
    { id: 1, name: "Last 7 days" },
    { id: 2, name: "Last 30 days" },
    { id: 3, name: "Last 90 days" },
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div className="mb-10">
            <h2 className="text-h6 mb-4 pb-2 border-b border-s">{title}</h2>
            {children}
        </div>
    );
}

function SubLabel({ children }: { children: React.ReactNode }) {
    return <span className="text-caption text-t-secondary mt-1">{children}</span>;
}

export default function ShowcasePage() {
    // Search state
    const [searchValue, setSearchValue] = useState("");
    const [searchGrayValue, setSearchGrayValue] = useState("");

    // Tabs state
    const [tabValue, setTabValue] = useState("tab1");
    const [iconTabValue, setIconTabValue] = useState("grid");

    // Field state
    const [fieldText, setFieldText] = useState("");
    const [fieldArea, setFieldArea] = useState("");
    const [fieldError] = useState("This field is required");

    // Checkbox state
    const [checked1, setChecked1] = useState(false);
    const [checked2, setChecked2] = useState(true);

    // Switch state
    const [switchOn, setSwitchOn] = useState(false);
    const [switchOn2, setSwitchOn2] = useState(true);

    // Select state
    const [selectValue, setSelectValue] = useState(selectOptions[0]);
    const [selectBlack, setSelectBlack] = useState(selectOptions[1]);

    // Modal state
    const [modalOpen, setModalOpen] = useState(false);
    const [slidePanelOpen, setSlidePanelOpen] = useState(false);

    // Table state
    const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set());
    const allSelected = selectedRows.size === 3;

    const toggleRow = (id: number, checked: boolean) => {
        const next = new Set(selectedRows);
        if (checked) next.add(id);
        else next.delete(id);
        setSelectedRows(next);
    };

    return (
        <div className="max-w-5xl mx-auto py-8 px-6">
            <h1 className="text-h4 mb-2">Core 2 Components</h1>
            <p className="text-body-1 text-t-secondary mb-8">
                Visual reference for all ported Core 2 design system components.
            </p>

            {/* 1. Icon */}
            <Section title="Icon">
                <div className="grid grid-cols-6 gap-4">
                    {iconNames.map((name) => (
                        <div
                            key={name}
                            className="flex flex-col items-center gap-2 p-3 rounded-2xl bg-b-surface1"
                        >
                            <Icon name={name} fill="#101010" />
                            <span className="text-caption text-t-secondary truncate w-full text-center">
                                {name}
                            </span>
                        </div>
                    ))}
                </div>
            </Section>

            {/* 2. Button */}
            <Section title="Button">
                <div className="flex flex-wrap items-center gap-4">
                    <div className="flex flex-col items-center gap-1">
                        <Button isBlack>Black</Button>
                        <SubLabel>isBlack</SubLabel>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                        <Button isWhite>White</Button>
                        <SubLabel>isWhite</SubLabel>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                        <Button isGray>Gray</Button>
                        <SubLabel>isGray</SubLabel>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                        <Button isStroke>Stroke</Button>
                        <SubLabel>isStroke</SubLabel>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                        <Button isBlack isCircle icon="plus" />
                        <SubLabel>isCircle</SubLabel>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                        <Button isGray icon="arrow-right">
                            With Icon
                        </Button>
                        <SubLabel>icon prop</SubLabel>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                        <Button isStroke disabled>
                            Disabled
                        </Button>
                        <SubLabel>disabled</SubLabel>
                    </div>
                </div>
            </Section>

            {/* 3. Card */}
            <Section title="Card">
                <div className="grid grid-cols-2 gap-4">
                    <Card title="Simple Card">
                        <div className="p-4 text-body-2 text-t-secondary">
                            Card content goes here.
                        </div>
                    </Card>
                    <Card
                        title="With Select"
                        selectOptions={selectOptions}
                        selectValue={selectValue}
                        selectOnChange={setSelectValue}
                    >
                        <div className="p-4 text-body-2 text-t-secondary">
                            Card with header select control.
                        </div>
                    </Card>
                </div>
            </Section>

            {/* 4. Search */}
            <Section title="Search">
                <div className="grid grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1">
                        <Search
                            value={searchValue}
                            onChange={(e) => setSearchValue(e.target.value)}
                            placeholder="Search..."
                        />
                        <SubLabel>Standard</SubLabel>
                    </div>
                    <div className="flex flex-col gap-1">
                        <Search
                            value={searchGrayValue}
                            onChange={(e) => setSearchGrayValue(e.target.value)}
                            placeholder="Search (gray)..."
                            isGray
                        />
                        <SubLabel>isGray</SubLabel>
                    </div>
                </div>
            </Section>

            {/* 5. Percentage */}
            <Section title="Percentage">
                <div className="flex items-center gap-4">
                    <div className="flex flex-col items-center gap-1">
                        <Percentage value={24.5} />
                        <SubLabel>Positive</SubLabel>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                        <Percentage value={-12.8} />
                        <SubLabel>Negative</SubLabel>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                        <Percentage value={37.2} isLarge />
                        <SubLabel>Large</SubLabel>
                    </div>
                </div>
            </Section>

            {/* 6. Tabs */}
            <Section title="Tabs">
                <div className="flex flex-col gap-4">
                    <div className="flex flex-col gap-1">
                        <Tabs
                            items={[
                                { label: "Overview", value: "tab1" },
                                { label: "Analytics", value: "tab2" },
                                { label: "Reports", value: "tab3" },
                            ]}
                            value={tabValue}
                            onChange={setTabValue}
                        />
                        <SubLabel>Text tabs (active: {tabValue})</SubLabel>
                    </div>
                    <div className="flex flex-col gap-1">
                        <Tabs
                            items={[
                                { icon: "grid", value: "grid" },
                                { icon: "layers", value: "layers" },
                                { icon: "chart", value: "chart" },
                            ]}
                            value={iconTabValue}
                            onChange={setIconTabValue}
                        />
                        <SubLabel>Icon tabs (active: {iconTabValue})</SubLabel>
                    </div>
                </div>
            </Section>

            {/* 7. Field */}
            <Section title="Field">
                <div className="grid grid-cols-2 gap-4">
                    <Field
                        label="Text Input"
                        value={fieldText}
                        onChange={(e) => setFieldText(e.target.value)}
                        placeholder="Enter text..."
                    />
                    <Field
                        label="With Tooltip"
                        tooltip="This is a helpful tooltip explaining the field"
                        value=""
                        onChange={() => {}}
                        placeholder="Has tooltip..."
                    />
                    <Field
                        label="Textarea"
                        value={fieldArea}
                        onChange={(e) => setFieldArea(e.target.value)}
                        placeholder="Enter longer text..."
                        textarea
                    />
                    <Field
                        label="With Error"
                        value=""
                        onChange={() => {}}
                        placeholder="Invalid field"
                        error={fieldError}
                    />
                </div>
            </Section>

            {/* 8. Tooltip */}
            <Section title="Tooltip">
                <div className="flex items-center gap-8">
                    <div className="flex flex-col items-center gap-1">
                        <Tooltip content="Top tooltip" place="top" />
                        <SubLabel>Top</SubLabel>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                        <Tooltip content="Bottom tooltip" place="bottom" />
                        <SubLabel>Bottom</SubLabel>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                        <Tooltip content="Left tooltip" place="left" />
                        <SubLabel>Left</SubLabel>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                        <Tooltip content="Right tooltip" place="right" />
                        <SubLabel>Right</SubLabel>
                    </div>
                </div>
            </Section>

            {/* 9. Checkbox */}
            <Section title="Checkbox">
                <div className="flex items-center gap-6">
                    <Checkbox label="Unchecked" checked={checked1} onChange={setChecked1} />
                    <Checkbox label="Checked" checked={checked2} onChange={setChecked2} />
                </div>
            </Section>

            {/* 10. Switch */}
            <Section title="Switch">
                <div className="flex items-center gap-6">
                    <Switch label="Off" checked={switchOn} onChange={setSwitchOn} />
                    <Switch label="On" checked={switchOn2} onChange={setSwitchOn2} />
                </div>
            </Section>

            {/* 11. Select */}
            <Section title="Select">
                <div className="grid grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1">
                        <Select
                            value={selectValue}
                            onChange={setSelectValue}
                            options={selectOptions}
                        />
                        <SubLabel>Standard</SubLabel>
                    </div>
                    <div className="flex flex-col gap-1">
                        <Select
                            value={selectBlack}
                            onChange={setSelectBlack}
                            options={selectOptions}
                            isBlack
                        />
                        <SubLabel>isBlack</SubLabel>
                    </div>
                </div>
            </Section>

            {/* 12. Modal */}
            <Section title="Modal">
                <div className="flex items-center gap-4">
                    <Button isStroke onClick={() => setModalOpen(true)}>
                        Open Center Modal
                    </Button>
                    <Button isStroke onClick={() => setSlidePanelOpen(true)}>
                        Open Slide Panel
                    </Button>
                </div>
                <Modal
                    title="Center Modal"
                    isOpen={modalOpen}
                    onClose={() => setModalOpen(false)}
                >
                    <p className="text-body-2 text-t-secondary mb-4">
                        This is a centered modal dialog. It supports a title, close button, and any content.
                    </p>
                    <div className="flex justify-end gap-3">
                        <Button isGray onClick={() => setModalOpen(false)}>Cancel</Button>
                        <Button isBlack onClick={() => setModalOpen(false)}>Confirm</Button>
                    </div>
                </Modal>
                <Modal
                    title="Slide Panel"
                    isOpen={slidePanelOpen}
                    onClose={() => setSlidePanelOpen(false)}
                    isSlidePanel
                >
                    <div className="p-6">
                        <p className="text-body-2 text-t-secondary">
                            This is a slide panel that opens from the right edge.
                        </p>
                    </div>
                </Modal>
            </Section>

            {/* 13. Dropdown */}
            <Section title="Dropdown">
                <div className="flex items-center gap-4">
                    <Dropdown
                        items={[
                            { label: "Edit", icon: "settings", onClick: () => {} },
                            { label: "Duplicate", icon: "layers", onClick: () => {} },
                            { label: "Delete", icon: "trash", onClick: () => {}, danger: true },
                        ]}
                    />
                </div>
            </Section>

            {/* 14. Table + TableRow */}
            <Section title="Table + TableRow">
                <Card title="Sample Table" className="!p-0 overflow-hidden">
                    <Table
                        headers={["Name", "Status", "Value"]}
                        selectAll
                        allSelected={allSelected}
                        onSelectAll={(checked) => {
                            if (checked) setSelectedRows(new Set([1, 2, 3]));
                            else setSelectedRows(new Set());
                        }}
                    >
                        <TableRow
                            selectable
                            selected={selectedRows.has(1)}
                            onSelect={(c) => toggleRow(1, c)}
                        >
                            <td className="py-3 px-4 text-body-2">Project Alpha</td>
                            <td className="py-3 px-4"><span className="label-green">Active</span></td>
                            <td className="py-3 px-4 text-body-2">$12,400</td>
                        </TableRow>
                        <TableRow
                            selectable
                            selected={selectedRows.has(2)}
                            onSelect={(c) => toggleRow(2, c)}
                        >
                            <td className="py-3 px-4 text-body-2">Project Beta</td>
                            <td className="py-3 px-4"><span className="label-yellow">Pending</span></td>
                            <td className="py-3 px-4 text-body-2">$8,200</td>
                        </TableRow>
                        <TableRow
                            selectable
                            selected={selectedRows.has(3)}
                            onSelect={(c) => toggleRow(3, c)}
                        >
                            <td className="py-3 px-4 text-body-2">Project Gamma</td>
                            <td className="py-3 px-4"><span className="label-red">Cancelled</span></td>
                            <td className="py-3 px-4 text-body-2">$3,100</td>
                        </TableRow>
                    </Table>
                </Card>
            </Section>

            {/* 15. Labels */}
            <Section title="Labels">
                <div className="flex flex-wrap items-center gap-3">
                    <span className="label-green">Green</span>
                    <span className="label-red">Red</span>
                    <span className="label-yellow">Yellow</span>
                    <span className="label-gray">Gray</span>
                    <span className="label-blue">Blue</span>
                    <span className="label-orange">Orange</span>
                    <span className="label-purple">Purple</span>
                </div>
            </Section>

            {/* 16. Spinner */}
            <Section title="Spinner">
                <div className="flex items-center gap-6">
                    <div className="flex flex-col items-center gap-1">
                        <Spinner />
                        <SubLabel>Default</SubLabel>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                        <Spinner className="!size-10 !border-4" />
                        <SubLabel>Large</SubLabel>
                    </div>
                </div>
            </Section>

            {/* 17. Image */}
            <Section title="Image">
                <div className="flex items-center gap-4">
                    <Image
                        className="w-24 h-24 rounded-2xl object-cover"
                        src="https://placehold.co/96x96/f1f1f1/727272?text=Core2"
                        alt="Placeholder"
                    />
                    <span className="text-body-2 text-t-secondary">
                        Image with fade-in on load
                    </span>
                </div>
            </Section>
        </div>
    );
}
