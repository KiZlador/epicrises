export class ApiError extends Error {
    constructor(message, status, data = {}) {
        super(message);
        this.status = status;
        this.data = data;
    }
}

export function createApi(fetcher = fetch) {
    async function request(url, options = {}) {
        let response;
        try {
            response = await fetcher(url, options);
        } catch {
            throw new ApiError("Не удалось связаться с сервером", 0);
        }
        if (!response.ok) {
            const data = await response.json().catch(() => null) || {};
            throw new ApiError(data.error || `Ошибка запроса (${response.status})`, response.status, data);
        }
        return response;
    }

    async function json(url, options) {
        const response = await request(url, options);
        try {
            return await response.json();
        } catch {
            throw new ApiError("Не удалось прочитать ответ сервера", response.status);
        }
    }

    async function result(name) {
        try {
            return await json("/result/" + encodeURIComponent(name));
        } catch (error) {
            if (error.status === 404) return null;
            throw error;
        }
    }

    return {
        listFiles: async () => (await json("/files")).files,
        deleteFile: (name) => json("/files/" + encodeURIComponent(name), { method: "DELETE" }),
        clearFiles: () => json("/files", { method: "DELETE" }),
        async upload(files) {
            const body = new FormData();
            for (const file of files) body.append("files", file);
            return json("/upload", { method: "POST", body });
        },
        startJob: () => json("/process", { method: "POST" }),
        jobStatus: () => json("/process/status"),
        async document(name) {
            const [data, source] = await Promise.all([
                result(name),
                json("/source/" + encodeURIComponent(name)),
            ]);
            return { result: data, source };
        },
        download: async (params) => (await request("/download?" + new URLSearchParams(params))).blob(),
        features: () => json(new URL("./features.json", import.meta.url)),
    };
}
