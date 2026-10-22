export function fileState(files, selected, busy) {
    const processedCount = files.filter((file) => file.processed).length;
    const pendingCount = files.length - processedCount;
    return {
        selected,
        busy,
        processedCount,
        pendingCount,
        selectedProcessed: files.some((file) => file.name === selected && file.processed),
        canProcess: !busy && pendingCount > 0,
        canClear: !busy && files.length > 0,
    };
}
