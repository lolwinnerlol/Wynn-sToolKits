#include <vector>
#include <algorithm>
#include <cmath>
#include <map>

// Export macro for Windows DLL
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

extern "C" {

    struct VertexWeight {
        int group_index;
        float weight;
    };

    bool compareWeights(const VertexWeight& a, const VertexWeight& b) {
        return a.weight > b.weight;
    }

    // Fixed stride for weight storage (Group Index, Weight Value)
    // We allow up to 8 weights per vertex in storage, but clamp to 4 for output.
    const int MAX_STORAGE = 8;
    const int MAX_INFLUENCE = 8;

    /**
     * Optimized Smoothing with Strided Data and In-Place Updates
     * 
     * Pointers:
     * - adj_starts/indices/weights: Standard CSR graph (Read Only)
     * 
     * - weight_indices: [num_verts * MAX_STORAGE] (Read/Write)
     * - weight_values:  [num_verts * MAX_STORAGE] (Read/Write)
     * 
     * - target_indices: Vertices to process
     * - num_targets: Count
     * - factor: usage varies (0.0 - 1.0)
     */
    EXPORT void smooth_strided(
        const int* adj_starts,
        const int* adj_indices,
        const float* adj_weights,
        
        int* weight_indices,
        float* weight_values,
        
        const int* target_indices,
        int num_targets,
        float factor
    ) {
        float inv_factor = 1.0f - factor;

        // We need a temp buffer for the NEW weights to avoid reading partially updated state?
        // Actually, pure smoothing usually wants snapshot state. 
        // If we write back immediately, the next vertex might read the SMOOTHED value of its neighbor.
        // This is "Seidel" iteration vs "Jacobi". 
        // Seidel (immediate write) converges faster but is order-dependent.
        // Jacobi (buffer write) is stable.
        // Visual brushes usually prefer Seidel (smearing feel).
        // BUT strict correctness suggests Jacobi. 
        // Given we process a "Subset" (Brush Radius), order dependence is minimal visually.
        // To be safe and maximize speed optimization (avoid allocs), we will try Immediate Write first.
        
        // HOWEVER: If we write fewer weights than existed, we must ensure we clean up.

        for (int t = 0; t < num_targets; ++t) {
            int v_idx = target_indices[t];
            
            // Map: GroupIndex -> WeightedSum
            // Using a small local buffer/vector is faster than std::map for <10 items
            // But map is easiest to write. Optimization: Use stack vector.
            std::map<int, float> accum_weights;

            // 1. Accumulate Neighbors
            int n_start = adj_starts[v_idx];
            int n_end = adj_starts[v_idx + 1];
            
            float total_edge_w = 0.0f;

            for (int i = n_start; i < n_end; ++i) {
                int n_idx = adj_indices[i];
                float edge_w = adj_weights[i];
                total_edge_w += edge_w;

                // Read neighbor weights from Strided Array
                int base = n_idx * MAX_STORAGE;
                for (int k = 0; k < MAX_STORAGE; ++k) {
                    int g = weight_indices[base + k];
                    float w = weight_values[base + k];
                    if (g < 0 || w <= 0.0f) continue; // Empty slot
                    
                    accum_weights[g] += (w * edge_w);
                }
            }

            // 2. Blend
            std::vector<VertexWeight> blended_weights;
            
            int v_base = v_idx * MAX_STORAGE;

            if (total_edge_w > 0.00001f) {
                float inv_total_edge = 1.0f / total_edge_w;

                // Accumulate current vertex weights into the map logic or separate?
                // Logic: New = Current*InvF + Avg*F
                
                // Get all potential groups (Neighbors + Self)
                // We iterate the map (Neighbors)
                for (auto& [g_idx, w_sum] : accum_weights) {
                    float avg_w = w_sum * inv_total_edge;
                    
                    // Find current weight in self
                    float cur_w = 0.0f;
                    for (int k = 0; k < MAX_STORAGE; ++k) {
                        if (weight_indices[v_base + k] == g_idx) {
                            cur_w = weight_values[v_base + k];
                            break;
                        }
                    }

                    float new_w = (cur_w * inv_factor) + (avg_w * factor);
                    if (new_w > 0.0001f) {
                        blended_weights.push_back({g_idx, new_w});
                    }
                }
                
                // Add Self-Only groups (not in neighbors)
                for (int k = 0; k < MAX_STORAGE; ++k) {
                    int g = weight_indices[v_base + k];
                    float w = weight_values[v_base + k];
                    if (g < 0 || w <= 0.0f) continue;
                     
                    if (accum_weights.find(g) == accum_weights.end()) {
                        float new_w = w * inv_factor;
                        if (new_w > 0.0001f) {
                            blended_weights.push_back({g, new_w});
                        }
                    }
                }

            } else {
                 // No neighbors? Keep as is.
                 continue; 
            }

            // 3. Limit & Sort
            std::sort(blended_weights.begin(), blended_weights.end(), compareWeights);
            
            if (blended_weights.size() > MAX_INFLUENCE) {
                blended_weights.resize(MAX_INFLUENCE);
            }

            // Normalize
            float total_final = 0.0f;
            for (const auto& vw : blended_weights) total_final += vw.weight;

            // 4. Write Back to Strided Array
            // Clear current slots first (or just overwrite)
            // We overwrite and set remainder to -1/0.0
            
            if (total_final > 0.00001f) {
                float ratio = 1.0f / total_final;
                int count = 0;
                for (const auto& vw : blended_weights) {
                    weight_indices[v_base + count] = vw.group_index;
                    weight_values[v_base + count] = vw.weight * ratio;
                    count++;
                }
                // Zero out remaining slots
                for (int k = count; k < MAX_STORAGE; ++k) {
                    weight_indices[v_base + k] = -1;
                    weight_values[v_base + k] = 0.0f;
                }
            } else {
                // Zero all
                for (int k = 0; k < MAX_STORAGE; ++k) {
                     weight_indices[v_base + k] = -1;
                     weight_values[v_base + k] = 0.0f;
                }
            }
        }
    }
    /**
     * Optimized Vertex Logic (Smear / Harden)
     * Does NOT use Adjacency (Vertex independent)
     * 
     * target_factors: Per-vertex factor (strength * falloff)
     */
    EXPORT void apply_vertex_logic_strided(
        int* weight_indices,
        float* weight_values,
        const int* target_indices,
        const float* target_factors,
        int num_targets,
        int active_group_index,
        int mode, // 0=Smear, 1=Harden
        float smear_value
    ) {
        for (int t = 0; t < num_targets; ++t) {
            int v_idx = target_indices[t];
            float factor = target_factors[t];
            int v_base = v_idx * MAX_STORAGE;
            
            // 1. Read Current Weights
            VertexWeight weights[MAX_STORAGE];
            int count = 0;
            float cur_w = 0.0f;
            
            for(int k=0; k<MAX_STORAGE; ++k) {
                int g = weight_indices[v_base + k];
                float w = weight_values[v_base + k];
                if (g >= 0 && w > 0.0f) {
                    weights[count++] = {g, w};
                    if (g == active_group_index) {
                         cur_w = w;
                    }
                }
            }
            
            // 2. Compute New Weight
            float new_w = cur_w;
            
            if (mode == 0) { // Smear
                 // If smear_value is -1, usually we do nothing, but Python handles that check.
                 // checking here just in case.
                 if (smear_value >= 0.0f) {
                     new_w = cur_w + (smear_value - cur_w) * factor;
                 }
            } else if (mode == 1) { // Harden (Contrast Stretch)
                // Old: Snap to 0 or 1. Discontinuous.
                // New: Push away from 0.5. Smooth.
                // new = cur + (cur - 0.5) * factor
                // If factor=1.0, this maps [0.25, 0.75] -> [0, 1].
                new_w = cur_w + (cur_w - 0.5f) * factor;

                // Clamp
                if (new_w < 0.0f) new_w = 0.0f;
                if (new_w > 1.0f) new_w = 1.0f;
            }
            
            if (std::abs(new_w - cur_w) < 0.0001f) continue;

            // 3. Update Buffer
            bool found = false;
            for(int k=0; k<count; ++k) {
                if (weights[k].group_index == active_group_index) {
                    weights[k].weight = new_w;
                    found = true;
                    break;
                }
            }
            if (!found && new_w > 0.0001f) {
                if (count < MAX_STORAGE) {
                    weights[count++] = {active_group_index, new_w};
                } else {
                     // Replace smallest if new_w is significant?
                     // Simplest: Replace index 0 if not active? 
                     // Or just ignore. (Matches simple Python add)
                     // Implementation: Sort by weight ascending and replace first if smaller?
                     // Let's blindly replace last one if full (or better: do proper sort limit)
                }
            }
            
            // 4. Sort & Limit & Normalize
            std::sort(weights, weights + count, compareWeights); // usages ptr math
            
            int final_count = (count > MAX_INFLUENCE) ? MAX_INFLUENCE : count;
            
            float total = 0.0f;
            for(int k=0; k<final_count; ++k) total += weights[k].weight;
            
            // Normalize
            if (total > 0.00001f) {
                float ratio = 1.0f / total;
                // Write back
                int write_cursor = 0;
                for(int k=0; k<final_count; ++k) {
                     weight_indices[v_base + write_cursor] = weights[k].group_index;
                     weight_values[v_base + write_cursor] = weights[k].weight * ratio;
                     write_cursor++;
                }
                 // Zero remainder
                for(int k=write_cursor; k<MAX_STORAGE; ++k) {
                    weight_indices[v_base + k] = -1;
                    weight_values[v_base + k] = 0.0f;
                }
            } else {
                 // Zero all
                for(int k=0; k<MAX_STORAGE; ++k) {
                    weight_indices[v_base + k] = -1;
                    weight_values[v_base + k] = 0.0f;
                }
            }
        }
    }
    /**
     * Build Adjacency Graph (CSR) from Raw Edges
     * Replaces slow Python loop.
     * 
     * edge_indices: [num_edges * 2] (flattened pairs)
     * vert_coords: [num_verts * 3] (flattened x,y,z)
     * 
     * Output:
     * adj_starts: [num_verts + 1] (Pre-allocated)
     * adj_indices: [num_edges * 2] (Pre-allocated)
     * adj_weights: [num_edges * 2] (Pre-allocated)
     */
    EXPORT void build_adjacency_graph(
        int num_verts,
        int num_edges,
        const int* edge_indices,
        const float* vert_coords,
        int* adj_starts,
        int* adj_indices,
        float* adj_weights
    ) {
        // 1. Calculate Degree per Vertex
        // Using adj_starts temporarily as counts
        std::fill(adj_starts, adj_starts + num_verts + 1, 0);

        for (int i = 0; i < num_edges; ++i) {
            int v1 = edge_indices[i * 2];
            int v2 = edge_indices[i * 2 + 1];
            adj_starts[v1]++;
            adj_starts[v2]++;
        }

        // 2. Prefix Sum -> Starts (CSR format)
        int current_cursor = 0;
        for (int i = 0; i < num_verts; ++i) {
            int count = adj_starts[i];
            adj_starts[i] = current_cursor;
            current_cursor += count;
        }
        adj_starts[num_verts] = current_cursor;

        // 3. Populate (Need temp cursors to track insertion position)
        // We can allocate a temp vector for current written count
        std::vector<int> current_pos(num_verts);
        for(int i=0; i<num_verts; ++i) current_pos[i] = adj_starts[i];

        for (int i = 0; i < num_edges; ++i) {
            int v1 = edge_indices[i * 2];
            int v2 = edge_indices[i * 2 + 1];

            // Calc Distance
            float x1 = vert_coords[v1*3];
            float y1 = vert_coords[v1*3+1];
            float z1 = vert_coords[v1*3+2];
            
            float x2 = vert_coords[v2*3];
            float y2 = vert_coords[v2*3+1];
            float z2 = vert_coords[v2*3+2];

            float dx = x1 - x2;
            float dy = y1 - y2;
            float dz = z1 - z2;
            float dist_sq = dx*dx + dy*dy + dz*dz;
            float dist = std::sqrt(dist_sq);
            float weight = 1.0f / (dist + 0.0001f);

            // Add v2 to v1 list
            int pos1 = current_pos[v1]++;
            adj_indices[pos1] = v2;
            adj_weights[pos1] = weight;

            // Add v1 to v2 list
            int pos2 = current_pos[v2]++;
            adj_indices[pos2] = v1;
            adj_weights[pos2] = weight;
        }
    }
}
