type SpinnerProps = {
    className?: string;
};

const Spinner = ({ className }: SpinnerProps) => (
    <div
        className={`inline-flex size-6 animate-spin rounded-full border-2 border-shade-08 border-t-blue ${className || ""}`}
    />
);

export default Spinner;
